import struct
from binascii import hexlify
import uasyncio

from umodbus import log
from umodbus.route import Map
from umodbus.functions import create_function_from_request_pdu
from umodbus.exceptions import ModbusError, ServerDeviceFailureError
from umodbus.utils import (get_function_code_from_request_pdu,
                           pack_exception_pdu)
from umodbus.client.serial.redundancy_check import CRCError


def get_server(server_class, serial_port):
    """ Return instance of :param:`server_class` with :param:`request_handler`
    bound to it.
    This method also binds a :func:`route` method to the server instance.
        >>> server = get_server(RTUServer, uart)
        >>> server.serve_forever()
    :param server_class: (sub)Class of :class:`umodbus.server.serial.RTUServer`.
    :param serial_port: (sub)Class of :class:`machine.UART`.
    :return: Instance of :param:`server_class`.
    """
    s = server_class()
    s.serial_port = serial_port

    s.route_map = Map()

    return s


class AbstractSerialServer(object):
    _shutdown_request = False

    def route(self, slave_ids=None, function_codes=None, addresses=None):
        """ A decorator that is used to register an endpoint for a given
        rule::

            @server.route(slave_ids=[1], function_codes=[1, 2], addresses=list(range(100, 200)))  # NOQA
            def read_single_bit_values(slave_id, address):
                return random.choise([0, 1])

        Any argument can be omitted to match any value.

        :param slave_ids: A list (or iterable) of slave ids.
        :param function_codes: A list (or iterable) of function codes.
        :param addresses: A list (or iterable) of addresses.
        """
        def inner(f):
            self.route_map.add_rule(f, slave_ids, function_codes, addresses)
            return f

        return inner


    def get_meta_data(self, request_adu):
        """" Extract MBAP header from request adu and return it. The dict has
        4 keys: transaction_id, protocol_id, length and unit_id.

        :param request_adu: A bytearray containing request ADU.
        :return: Dict with meta data of request.
        """
        return {
            'unit_id': struct.unpack('>B', request_adu[:1])[0],
        }

    def get_request_pdu(self, request_adu):
        """ Extract PDU from request ADU and return it.

        :param request_adu: A bytearray containing request ADU.
        :return: An bytearray container request PDU.
        """
        return request_adu[1:-2]

    async def serve_once(self):
        """ Listen and handle 1 request. """
        raise NotImplementedError

    async def serve_forever(self):
        """ Wait for incomming requests. """

        while not self._shutdown_request:
            try:
                await self.serve_once()
            except CRCError as e:
                log.error('Can\'t handle request: {0}'.format(e))

    def process(self, request_adu):
        """ Process request ADU and return response.

        :param request_adu: A bytearray containing the ADU request.
        :return: A bytearray containing the response of the ADU request.
        """
        meta_data = self.get_meta_data(request_adu)
        request_pdu = self.get_request_pdu(request_adu)

        response_pdu = self.execute_route(meta_data, request_pdu)
        response_adu = self.create_response_adu(meta_data, response_pdu)

        return response_adu

    def execute_route(self, meta_data, request_pdu):
        """ Execute configured route based on requests meta data and request
        PDU.

        :param meta_data: A dict with meta data. It must at least contain
            key 'unit_id'.
        :param request_pdu: A bytearray containing request PDU.
        :return: A bytearry containing reponse PDU.
        """
        try:
            function = create_function_from_request_pdu(request_pdu)
            results =\
                function.execute(meta_data['unit_id'], self.route_map)

            try:
                # ReadFunction's use results of callbacks to build response
                # PDU...
                return function.create_response_pdu(results)
            except TypeError:
                # ...other functions don't.
                return function.create_response_pdu()
        except ModbusError as e:
            function_code = get_function_code_from_request_pdu(request_pdu)
            return pack_exception_pdu(function_code, e.error_code)
        except Exception as e:
            log.exception('Could not handle request: {0}.'.format(e))
            function_code = get_function_code_from_request_pdu(request_pdu)

            return pack_exception_pdu(function_code,
                                      ServerDeviceFailureError.error_code)

    def respond(self, response_adu):
        """ Send response ADU back to client.

        :param response_adu: A bytearray containing the response of an ADU.
        """
        log.debug('--> {0}'.format(hexlify(response_adu)))
        self.serial_port.write(response_adu)

    def shutdown(self):
        self._shutdown_request = True

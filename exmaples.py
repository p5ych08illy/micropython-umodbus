import uasyncio
import machine
from umodbus.client.serial import rtu
from umodbus.server.serial import get_server
from umodbus.server.serial.rtu import RTUServer


async def server_loop(server_instance):
    await server_instance.serve_forever()



uart_client = machine.UART(1, 9600, tx=4, rx=36, bits=8, parity=None, stop=1, timeout=1000, timeout_char=50)
uart_server = machine.UART(2, 115200, tx=16, rx=13, bits=8, parity=0, stop=1, timeout=1, timeout_char=0)

# Client
message = rtu.read_input_registers(1, 0x0001, 1) 
result = rtu.send_message(message, uart_client)


# Server
server = get_server(RTUServer, uart_server)

@server.route(slave_ids=[1], function_codes=[1, 3])
def read_data_store(slave_id, function_code, address):
    """" Return value of address. """
    return 0
    
@server.route(slave_ids=[1], function_codes=[5, 6], addresses=list(range(0, 10)))
def write_data_store(slave_id, function_code, address, value):
    """" Set value for address. """
    print('Write FC: {0} address:{1} value:{2}'.format(function_code, address, value))
    

event_loop = uasyncio.get_event_loop()
event_loop.create_task(server_loop(server))
event_loop.run_forever()

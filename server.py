# -*- coding: utf-8 -*-

import socket
import base64
import hashlib
import struct
from select import select

class HandshakeRequest(object):
    KEY_TAG = 'Sec-WebSocket-Key'
    VERSION_TAG = 'Sec-WebSocket-Version'
    VERSION = "13"
    def __init__(self, data):
        self._header = self._parse_header(data)

    def is_validate(self):
        if not self._header.has_key(self.KEY_TAG): return False
        if not self._header.has_key(self.VERSION_TAG): return False
        if self._header[self.VERSION_TAG] != self.VERSION: return False
        return True

    def response(self):
         return 'HTTP/1.1 101 Switching Protocols\r\n'\
                'Upgrade: websocket\r\n'\
                'Connection: Upgrade\r\n'\
                'Sec-WebSocket-Accept:' + self._accept_key() + '\r\n\r\n'
        
    def _accept_key(self):
        websocket_key = self._header[self.KEY_TAG]
        websocket_key += "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
        return base64.b64encode(hashlib.sha1(websocket_key).digest())
       
    def _parse_header(self, data):
        headers = dict()
        for l in data.splitlines():
            parts = l.split(": ", 1)
            if len(parts) != 2: continue
            headers[parts[0]] = parts[1]
        return headers

class WebSocket(object):
    PACKET_LENGTH_MASK = int('01111111', 2)
    PAYLOAD_LENGTH = 4
    def __init__(self, accept_socket):
        self._socket =  accept_socket

    def handshake(self):
        data = self._socket.recv(8192)
        if not len(data): return False
        request = HandshakeRequest(data)
        if not request.is_validate(): return False
        self._socket.send(request.response())
        return True

    def send(self, data):
        head = '\x81' # FIN:1, opcode:1, 10000001=\x81
        data_length = len(data)
        if data_length < 126: head += struct.pack('B', data_length)
        elif data_length <= 0xFFFF: head += struct.pack('!BH', 126, data_length)
        else: head += struct.pack('!BQ', 127, data_length)
        self._socket.send(head + data)

    def recv(self, size=8192):
        recv_data = self._socket.recv(size)
        if not len(recv_data): return False
        mask, raw = self._raw_data(recv_data)
        data = [chr(ord(byte) ^ ord(mask[index % self.PAYLOAD_LENGTH])) for index, byte in enumerate(raw)]
        return ''.join(data)
 
    def _raw_data(self, data):
        length = ord(data[1]) & self.PACKET_LENGTH_MASK
        if length == 126: begin, end = 4, 6
        elif length == 127: begin, end = 10, 14
        else: begin, end = 2, 6
        mask, raw = data[begin:end], data[end:]
        return mask, raw

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
socket_list = set()

def sendall(data):
    for sock in socket_list:
        if sock != server:
            sock.send(data)

def process(client, data): #you should change this method
    client.send(data)

def main(handle=process):
    port = 7000
    try:
        server.bind(('', port))
        server.listen(5)
    except Exception, e:
        print e
        exit()
    socket_list.add(server)
    print 'server start on port %d' % port
    clients = dict()
    while True:
        readables, w, e = select(socket_list, [], [])
        for sock in readables:
            if sock == server:
                conn, addr = sock.accept()
                client = WebSocket(conn)
                if not client.handshake(): continue;
                socket_list.add(conn)
                clients[conn] = client
            else:
                client = clients[sock]
                data = client.recv()
                if not data:
                    socket_list.remove(sock)
                    del clients[sock]
                else:
                    handle(client, data)

if __name__ == '__main__':
    main()

#UDP server

from socket import *

serverName = 'localhost'
serverPort = 12000
serverSocket = socket(AF_INET, SOCK_DGRAM)
serverSocket.bind(("", serverPort))
print("Ready to receive..")

print("Message log: ")

while True:
    message, clientAddress = serverSocket.recvfrom(2048)
    print(message)
    modifiedMessage = message.decode().upper()
    
    
    serverSocket.sendto(modifiedMessage.encode(), clientAddress)
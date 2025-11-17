#UDP client

from socket import *
invoice = 0
serverName = 'localhost'
serverPort = 12000
clientSocket = socket(AF_INET, SOCK_DGRAM)
while (True):

    message = input('Input lowercase sentence: ')
    clientSocket.sendto(message.encode(), (serverName, serverPort))
    modifiedMessage, serverAddress = clientSocket.recvfrom(2048)

    print(modifiedMessage.decode())
    invoice+=5
    if (invoice == 20):
        clientSocket.close()
        break
       
    #clientSocket.close()

print('Out of free conversions!', invoice)
print("Your free tier has expired! Upgrade to UpperCase Pro for increased limits: https://www.enteryourwebsite.com")

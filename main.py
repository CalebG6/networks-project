import socket
import threading
import os
import time
import random
import io
import sys
import struct
import datetime


class Neighbor:
    neighborID: int
    interested: bool # Are we interested in this neighbor
    bitfield: list[bool] 
    choked: bool # Are we choking this neighbor
    downloadSpeed: float
    hasFullFile: bool
    isInterested: bool
    def __init__(self, neighborID, interested, bitfield, choked, downloadSpeed, hasFullFile, isInterested=False):
        self.neighborID = neighborID
        self.interested = interested
        self.bitfield = bitfield
        self.choked = choked
        self.downloadSpeed = downloadSpeed
        self.hasFullFile = hasFullFile

# Peer info
class Peer:
    def __init__(self, id, hostname, port, hasFile):
        self.id = id
        self.hostname = hostname
        self.port = port
        self.hasFile = hasFile
    
    id:int
    hostname:str
    port:int
    hasFile:bool
    # neighbors: list[Neighbor]

# Common config class
class Common:
    def __init__(self, NumberOfPreferredNeighbors, UnchokingInterval, 
                 OptimisticUnchokingInterval, FileName, 
                 FileSize, PieceSize, NumberOfPieces):
        self.NumberOfPreferredNeighbors = NumberOfPreferredNeighbors
        self.UnchokingInterval = UnchokingInterval
        self.OptimisticUnchokingInterval = OptimisticUnchokingInterval
        self.FileSize = FileSize
        self.FileName = FileName
        self.PieceSize = PieceSize
        self.NumberOfPieces = NumberOfPieces
    NumberOfPreferredNeighbors: int
    UnchokingInterval: int
    OptimisticUnchokingInterval: int #seconds
    FileSize: int #bytes 
    FileName: str
    PieceSize: int
    NumberOfPieces: int

# Config files
def readConfigFile():
    
    with open("Common.cfg", "r") as f:
        # read lines in config file
        for line in f:
            if line.startswith("NumberOfPreferredNeighbors"):
                NumberOfPreferredNeighbors = int(line.split(" ")[1].strip())
            elif line.startswith("UnchokingInterval"):
                UnchokingInterval = int(line.split(" ")[1].strip())
            elif line.startswith("OptimisticUnchokingInterval"):
                OptimisticUnchokingInterval = int(line.split(" ")[1].strip())
            elif line.startswith("FileName"):
                FileName = line.split(" ")[1].strip()
            elif line.startswith("FileSize"):
                FileSize = int(line.split(" ")[1].strip())
            elif line.startswith("PieceSize"):
                PieceSize = int(line.split(" ")[1].strip())
            # Calculate number of pieces
            if FileSize and PieceSize:
                NumberOfPieces = (FileSize + PieceSize - 1) // PieceSize

    config = Common(NumberOfPreferredNeighbors, UnchokingInterval, OptimisticUnchokingInterval,
                    FileName, FileSize, PieceSize, NumberOfPieces)

    return config



def getPeerInfo():
    Peers = []
    with open("PeerInfo.cfg", 'r') as f:
    # read lines from peer info 
        for line in f: 
            parts = line.split(" ").strip()
            peer = Peer()
            peer.id = int(parts[0])
            peer.hostname = parts[1]
            peer.port = int(parts[2])
            peer.hasFile = parts[3] == '1'
            Peers.append(peer)

        return Peers


def createThreads(peers):
    threads = []
    # Change target function
    for peer in peers:
        t = threading.Thread(target=peer_thread, args=(peer,common,))
        threads.append(t)
    
    return threads

# Types of messages and their associated value
message_types = dict(
    chokeType=0,
    unchokeType=1,
    interestedType=2,
    notInterestedType=3,
    haveType=4,
    bitfieldType=5,
    requestType=6,
    pieceType=7
)

# Create the handshake message
def makeHandshake(id):
    HandshakeHeader = "P2PFILESHARINGPROJ"
    HandshakeZeros = "\x00" * 10
    return HandshakeHeader + HandshakeZeros + struct.pack(id)

# Read the handshake message
def readHandshake(data):
    header = data[:18]
    if header != "P2PFILESHARINGPROJ":
        raise ValueError("Invalid handshake header")
    peerID = struct.unpack(">I", data[28:32])[0]
    return peerID

# Make a message
# message length is message type plus payload length, excludes message length field
def makeMessage(messageType, payload):
    if messageType not in message_types:
        raise ValueError(f"Invald message type: {messageType}")
    messageLength = 1 + len(payload)
    return struct.pack(">I", messageLength) + struct.pack("B", messageType) + payload

# Create the have message
def makeHaveMessage(pieceIndex):
    return makeMessage(message_types['haveType'], struct.pack(">I", pieceIndex))

# Create the bitfield message
def makeBitfieldMessage(bitfieldBytes):
    return makeMessage(message_types['bitfieldType'], bitfieldBytes)
# Create the request message
def makeRequestMessage(pieceIndex):
    return makeMessage(message_types['requestType'], struct.pack(">I", pieceIndex))

# Create the piece message
def makePieceMessage(pieceIndex, pieceData):
    return makeMessage(message_types['pieceType'], struct.pack(">I", pieceIndex) + pieceData)

# Create the bitfield bytes
def makeBitfieldBytes(NumberOfPieces, haveAll=False):
    numberofBytes = (NumberOfPieces + 7) // 8
    if haveAll:
        bf = bytearray(b'\xff' * numberofBytes)
        leftoverBits = numberofBytes * 8 - NumberOfPieces
        if leftoverBits:
            bf[-1] = bf[-1] & (0xFF << leftoverBits)
    else:
        bf = bytearray(numberofBytes)
    return bytes(bf)

def hasPiece(bitfield, pieceIndex):
    byteIndex = pieceIndex // 8
    bitIndex = 7 - (pieceIndex % 8)
    return bool(bitfield[byteIndex] & (1 << bitIndex))







# Initial peer thread function
def peer_thread(peer, common, Peers):
    # Create a socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((peer.hostname, peer.port))
    s.listen(5)
    # print(f"Peer {peer.id} listening on {peer.hostname}:{peer.port}")
    for p in Peers:
        if p.id != peer.id:
            # Connect to the peer
            try:
                conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                conn.connect((p.hostname, p.port))
                print(f"Peer {peer.id} connected to peer {p.id}")
                write_logs(peer.id, f"Peer {peer.id} connected to peer {p.id}")
                # Handle the connection in a new thread
                threading.Thread(target=handle_connection, args=(conn, peer, common, Peers)).start()
            except Exception as e:
                print(f"Peer {peer.id} failed to connect to peer {p.id}: {e}")
                write_logs(peer.id, f"Peer {peer.id} failed to connect to peer {p.id}: {e}" )
    while True:
        conn, addr = s.accept()
        print(f"Peer {peer.id} accepted connection from {addr}")
        # Handle the connection in a new thread
        threading.Thread(target=handle_connection, args=(conn, peer, common, Peers)).start()
    



def handle_connection(conn, peer, common, Peers):
        # Read the handshake message
        data = conn.recv(1024).decode()
        n_id = readHandshake(data)
        # Send handshake response
        handshake_response = makeHandshake(peer.id)
        conn.send(handshake_response.encode())
        # Write the log message
        neighbor = (Neighbor(n_id, False, [0] * common.NumberOfPieces, False, 0.0, False))
        conn.send(makeBitfieldMessage(''.join(['1' if peer.hasFile else '0' for _ in range(common.NumberOfPieces)])).encode())
        n_bitfield = conn.recv(1024).decode()
        neighbor.bitfield = [b == '1' for b in n_bitfield[5:]]
        if(not peer.hasFile and any(neighbor.bitfield)):
            neighbor.interested = True
        neighbor.hasFullFile = neighbor.bitfield.count(True) == common.NumberOfPieces
        main_neighbor_loop(conn, peer, common, Peers, neighbor)
        
# This needs to be changed a lot and the name should be changed, this should handle reading messages from the neighbor of this thread
# Still need to add another funciton that will implement which neighbors are our perferred neighbors.
def main_neighbor_loop(conn, peer, common, Peers, neighbor):
    while True:
        try:
            data = conn.recv(1024)
            if not data:
                break
            message_length = struct.unpack(">I", data[:4])[0]
            message_type = struct.unpack("B", data[4:5])[0]
            payload = data[5:5+message_length-1]
            if message_type == message_types['interestedType']:
                neighbor.isInterested = True
                print(f"Peer {peer.id} received interested message from peer {neighbor.neighborID}")
                write_logs(peer.id, f"Peer {peer.id} received interested message from peer {neighbor.neighborID}")
            elif message_type == message_types['notInterestedType']:
                neighbor.isInterested = False
                print(f"Peer {peer.id} received not interested message from peer {neighbor.neighborID}")
                write_logs(peer.id, f"Peer {peer.id} received not interested message from peer {neighbor.neighborID}")
            elif message_type == message_types['haveType']:
                pieceIndex = struct.unpack(">I", payload)[0]
                neighbor.bitfield[pieceIndex] = True
                neighbor.hasFullFile = neighbor.bitfield.count(True) == common.NumberOfPieces
                print(f"Peer {peer.id} received have message from peer {neighbor.neighborID} for piece {pieceIndex}")
                write_logs(peer.id, f"Peer {peer.id} received have message from peer {neighbor.neighborID} for piece {pieceIndex}")
            elif message_type == message_types['bitfieldType']:
                neighbor.bitfield = [b == '1' for b in payload]
                neighbor.hasFullFile = neighbor.bitfield.count(True) == common.NumberOfPieces
                print(f"Peer {peer.id} received bitfield message from peer {neighbor.neighborID}")
                write_logs(peer.id, f"Peer {peer.id} received bitfield message from peer {neighbor.neighborID}")
            elif message_type == message_types['requestType']:
                pieceIndex = struct.unpack(">I", payload)[0]
                print(f"Peer {peer.id} received request message from peer {neighbor.neighborID} for piece {pieceIndex}")
                write_logs(peer.id, f"Peer {peer.id} received request message from peer {neighbor.neighborID} for piece {pieceIndex}")
            elif message_type == message_types['pieceType']:
                pieceIndex = struct.unpack(">I", payload[:4])[0]
                pieceData = payload[4:]
                print(f"Peer {peer.id} received piece message from peer {neighbor.neighborID} for piece {pieceIndex}")
                write_logs(peer.id, f"Peer {peer.id} received piece message from peer {neighbor.neighborID} for piece {pieceIndex}")
        except Exception as e:
            print(f"Peer {peer.id} error handling connection with peer {neighbor.neighborID}: {e}")
            write_logs(peer.id, f"Peer {peer.id} error handling connection with peer {neighbor.neighborID}: {e}" )
            break


def write_logs(peer_id, message):
    log_file = 'log_peer_{peer_id}.log'
    log = f"[{datetime.now()}] message"
    
    with open(log_file, 'a') as f:
        f.write(log)

if __name__ == "__main__":
    common = readConfigFile()
    Peers = getPeerInfo()
    threads = createThreads(Peers)
    for t in threads:
        t.start()
    for t in threads:
        t.join()
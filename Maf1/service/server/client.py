from __future__ import print_function

import logging
# service.server.
import grpc
import mafiahandler_pb2 as mafiahandler_pb2
import mafiahandler_pb2_grpc as mafiahandler_pb2_grpc
import socket
import os
import sys
import math
import time
import pika
import random
from multiprocessing import Process
from threading import Thread

serviceAddr = 'localhost:8080'
RabbitMQHostname = 'localhost'
ucid = -1
chatchannels = []
def CmdInput():
    return input()

def Register(name):
    global ucid
    global serviceAddr
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.Register(mafiahandler_pb2.RegQuery(typeId=ucid, Name=name))
    ucid = response.uniqueClientId
    return ucid
    
def UnRegister():
    global ucid
    global serviceAddr
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.UnRegister(mafiahandler_pb2.UnRegQuery(uniqueClientId=ucid))
    return response.resultId
    
def Update():
    global ucid
    global serviceAddr
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.Update(mafiahandler_pb2.StatusQuery(uniqueClientId=ucid))
    return response.State

def Act(action, target):
    global ucid
    global serviceAddr
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.Action(mafiahandler_pb2.ActionQuery(typeId=action,targetId=target,uniqueClientId=ucid))
    return response.resultId

def Chat(msg, chan):
    global ucid
    global serviceAddr
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.Chat(mafiahandler_pb2.ChatMessage(Msg=msg,channel=int(chan),uniqueClientId=ucid))
    if response.resultId == 0:
        return 1
    else:
        return 3
    

def ParseState(state):
    time, nplayers, stateinfo, players, comissarinfo, myrole, dend = state.split(':')
    time = int(time)
    nplayers = int(nplayers)
    comissarinfo = int(comissarinfo)
    myrole = int(myrole)
    dend = int(dend)
    stateinfo = list(map(int, stateinfo.split(' ')))
    players = list(map(str, players.split(' ')))
    return time, nplayers, stateinfo, players, comissarinfo, myrole, dend

def StatePrint(dtime, n, state, players, intel, myrole, dend):
    if (dtime % 2 == 0):
        print("[ DAY ", dtime // 2 + 1, "]")
        alivecnt = 0
        for i in range(len(state)):
            if (state[i] != -1):
                alivecnt += 1
        print("  ALIVE: ", alivecnt)
        alive = 0
        for i in range(len(state)):
            if (state[i] != -1):
                print(' ', i, ":", players[i])
        if intel != -1:
            print("  Comissar has intel on a player:", intel, ":", players[intel])
        if (dtime != 0 and myrole != -1 and dend == 0):
            print("Use VOTE {Number} to vote for a player to be executed this day")
        if (myrole != -1 and dend == 0):
            print("Use PASS to wait and refresh")
            print("Use END to end the day")
            print("Use SAY {Message} to chat with other people")
        if myrole == 2 and intel != -1 and dend == 0:
            print("Use PUBLISH to spread the intel on player", intel, ":", players[intel])
        if myrole == 1 and dend == 0:
            print("Use WHISPER {Message} to chat with other criminals")
        if myrole != -1:
            return True
        else:
            return False
    else:
        print("[ NIGHT ", dtime // 2 + 1, "]")
        alivecnt = 0
        for i in range(len(state)):
            if (state[i] != -1):
                alivecnt += 1
        print("  ALIVE: ", alivecnt)
        alive = 0
        for i in range(len(state)):
            if (state[i] != -1):
                print(' ', i, ":", players[i])
        if myrole == 1 and dend == 0:
            print("Use VOTE {Number} to vote for a player to be killed this night")
            print("Use END to end the night")
            print("Use WHISPER {Message} to chat with other criminals")
        if myrole == 2 and dend == 0:
            print("Use VOTE {Number} to vote for a player to be investigated this night")
            print("Use END to end the night")
        if myrole > 0:
            return True
        else:
            return False

def GameEngineBot():
    # Awaiting the game
    retrytimes = 10
    while True:
        time.sleep(3)
        code, msg = Update().split('|')
        code = int(code)
        if code == -1:
            print("[ERROR] Game session timed out")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == -2:
            print("[ERROR] Game already ended")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == -3:
            print("[ERROR] Registration expired")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == 0:
            print("[...] Waiting for the game to start (not enough players)")
            msg = list(map(str, msg.split(':')))
            print("Currently waiting players list:")
            print(msg)
        elif code == 1:
            print("[!] Started a new game session")
            break
        else:
            print("[ERROR] Something went wrong - unexpected update code:", code, "with message:", msg)
            print('Hint: use REGBOT {Name} again to start another round!')
            return
    # Game started, initial data
    extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend = ParseState(msg)
    _ = StatePrint(extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend)
    startrole = exmyrole
    if (startrole == 0):
        print("[ROLE] Civillian")
    if (startrole == 1):
        print("[ROLE] Criminal")
    if (startrole == 2):
        print("[ROLE] Comissar")
    extime = -1
    while True:
        code, msg = Update().split('|')
        code = int(code)
        if code == -1:
            print("[ERROR] Game session timed out, start over")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == -2:
            print("[ERROR] Game already ended")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == -3:
            print("[ERROR] Registration expired")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == 0:
            print("[ERROR] Unexpected waiting code")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        elif code == 1:
            dtime, nplayers, stateinfo, players, comissarinfo, myrole, dend = ParseState(msg)
            if dtime != extime or stateinfo != exstateinfo or explayers != players or comissarinfo != excomissarinfo:
                extime, exstateinfo, explayers, excomissarinfo, exmyrole, exdend = dtime, stateinfo, players, comissarinfo, myrole, dend
                action = StatePrint(extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend)
                if action:
                    while True:
                        print("Time to act!")
                        aliveid = []
                        for i in range(nplayers):
                            if exstateinfo[i] == 0:
                                aliveid.append(i)
                        # Bot randomizer
                        act = random.randint(0, 1)
                        if act == 0:
                            act = 'END'
                        else:
                            act = 'VOTE '
                            act += str(aliveid[random.randint(0, len(aliveid) - 1)])
                        res = -10
                        if (len(act) >= 4 and act[0:4] == 'VOTE'):
                            target = act[5:]
                            if (not target.isnumeric()):
                                print("Please specify a number as a target: VOTE {Target}")
                                continue
                            target = int(target)
                            res = Act(1, target)
                        elif (len(act) >= 3 and act[0:3] == 'END'):
                            res = Act(3, -1)
                        if res == -10:
                            print("Unknown command, try again")
                        elif res == -1:
                            print('[ERROR] Timed out or not registered')
                            return
                        elif res == 0:
                            print('[ERROR] Waiting for a game')
                            return
                        elif res == 1:
                            print('[INFO] Action success')
                            if (len(act) >= 3 and act[0:3] == 'END'):
                                break
                        elif res == 2:
                            print('[FAILURE] Day ended')
                            break
                        elif res == 3:
                            print('[FAILURE] Wrong phase (night)')
                            break
                        elif res == 4:
                            print('[FAILURE] You are dead')
                            break
                        elif res == 5:
                            print('[FAILURE] Wrong role')
                        elif res == 6:
                            print('[FAILURE] Cannot vote on first day')
                        else:
                            print('[FAILURE] Unknown command')
        elif code == 2:
            if (int(msg) == 1):
                if (startrole == 1):
                    print("[LOSS] ", end='')
                else:
                    print("[WIN] ", end='')
                print("Civillians won!")
                
            elif (int(msg) == -1):
                if (startrole == 1):
                    print("[WIN] ", end='')
                else:
                    print("[LOSS] ", end='')
                print("Criminals won!")
            print('Hint: use REGBOT {Name} again to start another round!')
            return
        else:
            print('Unknown message from server:', code, msg)
        time.sleep(1)

def GameEngine(inputfunction):
    # Awaiting the game
    retrytimes = 10
    while True:
        time.sleep(3)
        code, msg = Update().split('|')
        code = int(code)
        if code == -1:
            print("[ERROR] Game session timed out")
            print('Hint: use REG {Name} again to start another round!')
            return
        elif code == -2:
            print("[ERROR] Game already ended")
            print('Hint: use REG {Name} again to start another round!')
            return
        elif code == -3:
            print("[ERROR] Registration expired")
            print('Hint: use REG {Name} again to start another round!')
            return
        elif code == 0:
            print("[...] Waiting for the game to start (not enough players)")
            msg = list(map(str, msg.split(':')))
            print("Currently waiting players list:")
            print(msg)
            retrytimes -= 1
            if (retrytimes == 0):
                print("Specify a number of updates after which to ask again or type UNREG to leave the queue")
                something = inputfunction()
                if (something.isnumeric()):
                    retrytimes = int(something)
                elif (something == 'UNREG'):
                    res = UnRegister()
                    if res == 0:
                        print("[INFO] Successfully left the queue")
                        return
                    else:
                        print("[FAILURE] Can't leave the queue game found")
                else:
                    retrytimes = 1
        elif code == 1:
            print("[!] Started a new game session")
            break
        else:
            print("[ERROR] Something went wrong - unexpected update code:", code, "with message:", msg)
            print('Hint: use REG {Name} again to start another round!')
            return
    # Game started, initial data
    EnableChat()
    extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend = ParseState(msg)
    _ = StatePrint(extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend)
    startrole = exmyrole
    if (startrole == 0):
        print("[ROLE] Civillian")
    if (startrole == 1):
        print("[ROLE] Criminal")
    if (startrole == 2):
        print("[ROLE] Comissar")
    extime = -1
    while True:
        code, msg = Update().split('|')
        code = int(code)
        if code == -1:
            print("[ERROR] Game session timed out, start over")
            print('Hint: use REG {Name} again to start another round!')
            DisableChat()
            return
        elif code == -2:
            print("[ERROR] Game already ended")
            print('Hint: use REG {Name} again to start another round!')
            DisableChat()
            return
        elif code == -3:
            print("[ERROR] Registration expired")
            print('Hint: use REG {Name} again to start another round!')
            DisableChat()
            return
        elif code == 0:
            print("[ERROR] Unexpected waiting code")
            print('Hint: use REG {Name} again to start another round!')
            DisableChat()
            return
        elif code == 1:
            dtime, nplayers, stateinfo, players, comissarinfo, myrole, dend = ParseState(msg)
            if dtime != extime or stateinfo != exstateinfo or explayers != players or comissarinfo != excomissarinfo:
                extime, exstateinfo, explayers, excomissarinfo, exmyrole, exdend = dtime, stateinfo, players, comissarinfo, myrole, dend
                action = StatePrint(extime, nplayers, exstateinfo, explayers, excomissarinfo, exmyrole, exdend)
                if action:
                    while True:
                        print("Time to act!")
                        act = inputfunction()
                        res = -10
                        if (len(act) >= 4 and act[0:4] == 'VOTE'):
                            target = act[5:]
                            if (not target.isnumeric()):
                                print("Please specify a number as a target: VOTE {Target}")
                                continue
                            target = int(target)
                            res = Act(1, target)
                        elif (len(act) >= 7 and act[0:7] == 'PUBLISH'):
                            res = Act(2, -1)
                        elif (len(act) >= 3 and act[0:3] == 'END'):
                            res = Act(3, -1)
                        elif (len(act) >= 4 and act[0:4] == 'PASS'):
                            extime = -1
                            break
                        elif (len(act) >= 3 and act[0:3] == 'SAY'):
                            res = Chat(act[4:], chatchannels[0])
                        elif (len(act) >= 7 and act[0:7] == 'WHISPER'):
                            res = Chat(act[8:], chatchannels[1])
                        if res == -10:
                            print("Unknown command, try again")
                        elif res == -1:
                            print('[ERROR] Timed out or not registered')
                            DisableChat()
                            return
                        elif res == 0:
                            print('[ERROR] Waiting for a game')
                            DisableChat()
                            return
                        elif res == 1:
                            print('[INFO] Action success')
                            if (len(act) >= 3 and act[0:3] == 'END'):
                                break
                        elif res == 2:
                            print('[FAILURE] Day ended')
                            break
                        elif res == 3:
                            print('[FAILURE] Wrong phase (night)')
                            break
                        elif res == 4:
                            print('[FAILURE] You are dead')
                            break
                        elif res == 5:
                            print('[FAILURE] Wrong role')
                        elif res == 6:
                            print('[FAILURE] Cannot vote on first day')
                        else:
                            print('[FAILURE] Unknown command')
        elif code == 2:
            if (int(msg) == 1):
                if (startrole == 1):
                    print("[LOSS] ", end='')
                else:
                    print("[WIN] ", end='')
                print("Civillians won!")
                
            elif (int(msg) == -1):
                if (startrole == 1):
                    print("[WIN] ", end='')
                else:
                    print("[LOSS] ", end='')
                print("Criminals won!")
            print('Hint: use REG {Name} again to start another round!')
            DisableChat()
            return
        else:
            print('Unknown message from server:', code, msg)
        time.sleep(1)

def RegisterService():
    global serviceAddr
    serviceAddr = os.environ.get('SERVICE_ADDR', 'localhost:8080')       

chatthreads = []

def ChatThread(chans):
    chans = str(chans)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RabbitMQHostname))
    channel = connection.channel()
    channel.exchange_declare(exchange=chans, exchange_type='fanout')
    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue
    channel.queue_bind(exchange=chans, queue=queue_name)
    def callback(ch, method, properties, body):
        print(" [CHAT] %r" % body.decode('utf-8'))
    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True)
    channel.start_consuming()

def EnableChat():
    global ucid
    global serviceAddr
    global chatthreads
    global chatchannels
    with grpc.insecure_channel(serviceAddr) as channel:
        stub = mafiahandler_pb2_grpc.EngineServerStub(channel)
        response = stub.ChatQueue(mafiahandler_pb2.ChatGetQueue(uniqueClientId=ucid))
    if response.resultId > 0:
        print("[WARNING] Unable to connect to chat room. Chat functions will not work in this game!")
        return
    elif response.resultId == 0:
        chatchannels = [response.Queues]
        chatthreads = [0]
        chatthreads[0] = Process(target=ChatThread, args=[chatchannels[0]], daemon=True)
    elif response.resultId == -1:
        chatchannels = list(map(str, response.Queues.split(":")))
        chatthreads = [0, 0]
        chatthreads[0] = Process(target=ChatThread, args=[chatchannels[0]], daemon=True)
        chatthreads[1] = Process(target=ChatThread, args=[chatchannels[1]], daemon=True)
    for i in range(len(chatthreads)):
        chatthreads[i].start()
    return

def DisableChat():
    for i in range(len(chatthreads)):
        chatthreads[i].terminate()
    return

def printer(arg):
    print(arg)

def run():
    global serviceAddr
    RegisterService()
    global RabbitMQHost
    RabbitMQHost = os.environ.get('RABBITMQHOST', 'localhost')
    print("Commands:")
    print("    REG {Name} - registers you with that name for the next game (only letters and numbers)")
    print("    REGBOT {Name} - registers bot with that name for the next game (only letters and numbers")
    print("    SERVER {Address} - switches to specified server (DEFAULT will reset to default)")
    while True:
        cmd, arg = input().split()
        if cmd == 'REG':
            if (arg.isalnum()):
                Register(arg)
                GameEngine(CmdInput)
            else:
                print("Invalid name, only letters and numbers are allowed")
        elif cmd == 'REGBOT':
            if (arg.isalnum()):
                Register(arg)
                GameEngineBot()
            else:
                print("Invalid name, only letters and numbers are allowed")
        elif cmd == 'SERVER':
            if (arg == 'DEFAULT'):
                RegisterService()
            else:
                serviceAddr = arg
    name = input()


if __name__ == '__main__':
    logging.basicConfig()
    run()

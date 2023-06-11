from concurrent import futures
import logging

from threading import Lock

import grpc
import mafiahandler_pb2 as mafiahandler_pb2
import mafiahandler_pb2_grpc as mafiahandler_pb2_grpc
# service.server.
import os
import pika
import sys
import time
from random import shuffle

waitinglist = []
timedout = []
nextid = 1
games = []
ucidstatus = dict()

RabbitMQHostname = 'localhost'
maxphasetime = 90
playernumber = 8
rolescounts = [0, 2, 1]
TimedOutStatus = '-1|TimedOut'
GameEndStatus = '-2|GameEnded'
WHOTFRUStatus = '-3|WhoTheHellAreYou?'

class GameState:
    def __init__(self):
        self.started = False
        self.gameid = 0
        self.dtime = 0
        self.players = []
        self.roles = dict()
        self.startroles = dict()
        self.actions = dict()
        self.dend = []
        self.comissarcheck = -1
        self.comissarpublish = False
        self.startphasetime = -1
        self.mutex = Lock()
        self.ending = 0
        return

    def StartGame(self, gameId, players):
        self.gameid = gameId
        self.players = players
        ChatWrapper.InitRoom(self.gameid)
        self.dend = [False] * len(self.players)
        self.SetRoles()
        self.startroles = dict(self.roles)
        self.started = True
        self.startphasetime = time.time()
        return
    
    def Vote(self, ucid, target):
        if self.dtime == 0:
            return 6
        if self.roles[ucid] == -1:
            return 4
        if self.dend[self.players.index(ucid)]:
            return 2
        self.actions[ucid] = target
        return 1
        
    def Publish(self, ucid):
        if self.roles[ucid] == -1:
            return 4
        if self.roles[ucid] != 2:
            return 5
        if self.dend[self.players.index(ucid)]:
            return 2
        if self.dtime % 2 == 0:
            if self.comissarcheck != -1 and self.comissarpublish == False:
                self.comissarpublish = True
        else:
            return 3
        return 1
        
    def EndDay(self, ucid):
        if self.roles[ucid] == -1:
            return 4
        if self.dend[self.players.index(ucid)]:
            return 2
        self.dend[self.players.index(ucid)] = True
        return 1

    
    def Update(self, ucid):
        self.mutex.acquire()
        
        if self.ending != 0:
            res = '2|'
            res += str(self.ending)
            ucidstatus[ucid][1] = -5
            self.mutex.release()
            return res
        now = time.time()
        if now - self.startphasetime >= maxphasetime:
            self.EndPhase()
        if self.dtime % 2 == 0:
            endday = True
            for i in range(len(self.dend)):
                if not self.dend[i]:
                    endday = False
            if endday:
                self.EndPhase()
        elif self.dtime % 2 == 1:
            nightrolescnt = 0
            for key, value in self.roles.items():
                if value > 0:
                    nightrolescnt += 1
            endday = True
            for i in range(len(self.dend)):
                if (not self.dend[i]) and self.roles[self.players[i]] > 0:
                    endday = False
            if endday:
                self.EndPhase()
        
        if self.ending != 0:
            res = '2|'
            res += str(self.ending)
            ucidstatus[ucid][1] = -5
            self.mutex.release()
            return res
        res = '1|' + str(self.dtime) + ':' + str(len(self.players)) + ':'
        for i in range(len(self.players)):
            if (i != 0):
                res += ' '
            if (self.roles[self.players[i]] == -1):
                res += '-1'
            else:
                res += '0'
        res += ':'
        for i in range(len(self.players)):
            if (i != 0):
                res += ' '
            res += ucidstatus[self.players[i]][0]
        res += ':'
        if self.roles[ucid] == 2 or self.comissarpublish:
            res += str(self.comissarcheck)
        else:
            res += str(-1)
        res += ':'
        res += str(self.roles[ucid])
        res += ':'
        res += str((1 if self.dend[self.players.index(ucid)] else 0))
        self.mutex.release()
        return res

    def EndPhase(self):
        if self.dtime % 2 == 0:
            vote = [0] * len(self.players)
            for key, value in self.actions.items():
                vote[value] += 1
            tie = True
            maxind = 0
            maxvote = 0
            for i in range(len(self.players)):
                if vote[i] > maxvote:
                    maxvote = vote[i]
                    maxind = i
                    tie = False
                elif vote[i] == maxvote:
                    tie = True
            if not tie:
                self.roles[self.players[maxind]] = -1
            self.comissarcheck = -1
        else:
            vote = [0] * len(self.players)
            for key, value in self.actions.items():
                if (self.roles[key] == 1):
                    vote[value] += 1
            tie = True
            maxind = 0
            maxvote = 0
            for i in range(len(self.players)):
                if vote[i] > maxvote:
                    maxvote = vote[i]
                    maxind = i
                    tie = False
                elif vote[i] == maxvote:
                    tie = True
            if not tie:
                self.roles[self.players[maxind]] = -1
            
            vote = [0] * len(self.players)
            for key, value in self.actions.items():
                if (self.roles[key] == 2):
                    vote[value] += 1
            tie = True
            maxind = 0
            maxvote = 0
            for i in range(len(self.players)):
                if vote[i] > maxvote:
                    maxvote = vote[i]
                    maxind = i
                    tie = False
                elif vote[i] == maxvote:
                    tie = True
            if not tie:
                if (self.roles[self.players[maxind]] == 1):
                    self.comissarcheck = self.players[maxind]
        self.comissarpublish = False
        self.dend = [False] * len(self.players)
        for i in range(len(self.players)):
            if self.roles[self.players[i]] == -1:
                self.dend[i] = True
        self.actions = dict()
        self.dtime += 1
        balance = 0
        alive = 0
        self.startphasetime = time.time()
        for key, value in self.roles.items():
            if value == 1:
                balance -= 1
                alive += 1
            elif value != -1:
                balance += 1
                alive += 1
        return
            
        
    def SetRoles(self):
        roles = [0] * len(self.players)
        ii = 0
        for i in range(1, len(rolescounts)):
            for j in range(rolescounts[i]):
                roles[ii] = i
                ii += 1
        shuffle(roles)
        for i in range(len(self.players)):
            self.roles[self.players[i]] = roles[i]
        return

class ChatWrapperClass:
    def __init__(self):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RabbitMQHostname))
        self.chans = connection.channel()
    
    def InitRoom(self, gameid):
        self.chans.exchange_declare(exchange=str(2 * gameid + 150), exchange_type='fanout')
        self.chans.exchange_declare(exchange=str(2 * gameid + 151), exchange_type='fanout')

    def Send(self, ucid, msg, chanq):
        if (chanq % 2 == 0):
            truemsg = ucidstatus[ucid][0] + ' says >>> ' + msg
        elif (chanq % 2 == 1):
            truemsg = ucidstatus[ucid][0] + ' whispers >>> ' + msg
        self.chans.basic_publish(exchange=str(chanq), routing_key='', body=truemsg)

ChatWrapper = ChatWrapperClass()

class Servicer(mafiahandler_pb2_grpc.EngineServerServicer):

    def Register(self, request, context):
        print('[LOGS] Register', request.typeId)
        global nextid
        global waitinglist
        global ucidstatus
        typeId = request.typeId
        if (typeId == -1):
            Id, nextid = nextid, nextid + 1
            waitinglist.append(Id)
            ucidstatus[Id] = [request.Name, -5, 0, 0, 0]
        else:
            if typeId in ucidstatus:
                Id = typeId
                ucidstatus[Id][0] = request.Name
                if (ucidstatus[Id][1] == -5):
                    waitinglist.append(Id)
            else:
                Id = typeId
                ucidstatus[Id] = [request.Name, -5, 0, 0, 0]
                return mafiahandler_pb2.RegResponse(uniqueClientId=Id)
        return mafiahandler_pb2.RegResponse(uniqueClientId=Id)
        
    def UnRegister(self, request, context):
        print('[LOGS] UnRegister', request.uniqueClientId)
        global nextid
        global waitinglist
        global ucidstatus
        ucid = request.uniqueClientId
        if ucid in waitinglist:
            i = waitinglist.index(ucid)
            if i != len(waitinglist) - 1:
                waitinglist = waitinglist[:i] + waitinglist[i+1:]
            else:
                waitinglist = waitinglist[:-1]
            return mafiahandler_pb2.UnRegResponse(resultId=0)
        else:
            return mafiahandler_pb2.UnRegResponse(resultId=1)
        
    def Chat(self, request, context):
        print('[LOGS] CHAT', request.uniqueClientId, request.Msg, request.channel)
        global nextid
        global waitinglist
        global ucidstatus
        ucid = request.uniqueClientId
        game = ucidstatus[ucid][1]
        if game >= 0:
            if (request.channel % 2 == 0):
                if (games[game].dtime % 2 == 0):
                    ChatWrapper.Send(ucid, request.Msg, request.channel)
                    return mafiahandler_pb2.ChatResponse(resultId=0)
                else:
                    return mafiahandler_pb2.ChatResponse(resultId=1)
            else:
                if (games[game].roles[ucid] == 1):
                    ChatWrapper.Send(ucid, request.Msg, request.channel)
                    return mafiahandler_pb2.ChatResponse(resultId=0)
                else:
                    return mafiahandler_pb2.ChatResponse(resultId=1)
        else:
            return mafiahandler_pb2.ChatResponse(resultId=2)

    def ChatQueue(self, request, context):
        print('[LOGS] CHATQUEUE', request.uniqueClientId)
        global nextid
        global waitinglist
        global ucidstatus
        ucid = request.uniqueClientId
        game = ucidstatus[ucid][1]
        if game >= 0:
            qs = str(game * 2 + 150)
            if (games[game].roles[ucid] == 1):
                qs += ':'
                qs += str(game * 2 + 151)
                print('[EXLOGS] Qs:', qs)
                return mafiahandler_pb2.ChatQueueResponse(resultId=-1, Queues=qs)
            print('[EXLOGS] Qs:', qs)
            return mafiahandler_pb2.ChatQueueResponse(resultId=0, Queues=qs)
        else:
            return mafiahandler_pb2.ChatResponse(resultId=1, Queues='')

    def Update(self, request, context):    
        print('[LOGS] Update', request.uniqueClientId)
        global waitinglist
        global ucidstatus
        global games
        if len(waitinglist) >= playernumber:
            games.append(GameState())
            players = list(waitinglist)
            for i in range(len(waitinglist)):
                ucidstatus[waitinglist[i]][1] = len(games) - 1
            waitinglist = []
            games[-1].StartGame(len(games), players)
        ucid = request.uniqueClientId
        if (ucid in waitinglist):
            wl = '0|'
            for i in range(len(waitinglist)):
                wl += ucidstatus[waitinglist[i]][0]
                wl += ':'
            wl = wl[:-1]
            return mafiahandler_pb2.StatusResponse(State=wl, uniqueClientId=ucid)
        if (ucid in ucidstatus):
            if ucidstatus[ucid][1] == -1:
                return mafiahandler_pb2.StatusResponse(State=TimedOutStatus, uniqueClientId=ucid)
            elif ucidstatus[ucid][1] == -5:
                return mafiahandler_pb2.StatusResponse(State=GameEndStatus, uniqueClientId=ucid)
            return mafiahandler_pb2.StatusResponse(State=games[ucidstatus[ucid][1]].Update(ucid), uniqueClientId=ucid)
        return mafiahandler_pb2.StatusResponse(State=WHOTFRUStatus, uniqueClientId=ucid)
    
    def Action(self, request, context):
        global waitinglist
        global ucidstatus
        global games
        ucid = request.uniqueClientId
        print('[LOGS] Action', ucid, request.typeId)
        if (ucid in ucidstatus):
            if ucidstatus[ucid][1] < 0:
                return mafiahandler_pb2.ActionResponse(uniqueClientId=ucid, resultId=ucidstatus[ucid][1])
            res = -1
            if request.typeId == 1:
                res = games[ucidstatus[ucid][1]].Vote(ucid, request.targetId)
            elif request.typeId == 2:
                res = games[ucidstatus[ucid][1]].Publish(ucid)
            elif request.typeId == 3:
                res = games[ucidstatus[ucid][1]].EndDay(ucid)
            elif request.typeId == -1:
                res = games[ucidstatus[ucid][1]].Suicide(ucid)
                ucidstatus[ucid][1] = -1
            return mafiahandler_pb2.ActionResponse(uniqueClientId=ucid, resultId=res)
        return mafiahandler_pb2.ActionResponse(uniqueClientId=ucid, resultId=-1)

def serve():
    global RabbitMQHost
    global playernumber
    global maxphasetime
    global rolescount
    RabbitMQHost = os.environ.get('RABBITMQHOST', 'localhost')
    port = os.environ.get('SERVICE_PORT', '8080')
    maxphasetime = float(os.environ.get('MAX_PHASE_TIME', '90'))
    maxphasetime = int(os.environ.get('MAX_PLAYERS', '8'))
    rolescount[1] = int(os.environ.get('CRIM_CNT', '2'))
    rolescount[2] = int(os.environ.get('COMI_CNT', '1'))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    mafiahandler_pb2_grpc.add_EngineServerServicer_to_server(Servicer(), server)
    server.add_insecure_port('[::]:' + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()

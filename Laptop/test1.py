#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import numpy as np
import os
import argparse
import socket
import pickle
import json
import ast
import threading
import time
import datetime
import torch
from model import DNN, DNN_8
from torch.utils.data import DataLoader
from config import Config
from dataset import WifiData
import time
from visualization import Visualizer

class ClientThread():
    def __init__(self, config, host='192.168.137.183', port=8000):
        super(ClientThread, self).__init__()
        self.config = config
        self.data = []
        self.host = host
        self.port = port
        self.path = config.root + config.test_path + 'data' + self.host + 'temp.pkl'
        
        self.device = torch.device("cpu")
        parser = argparse.ArgumentParser(description='Wifi Indoor Positioning System')
        args = parser.parse_args()
        args.feat_dim = config.n_address
        args.dropout = 0.0
        self.model = DNN_8(args)
        self.model.load_state_dict(torch.load("./checkpoints/address_128_8_layer_jitter_0.05_valsplit_0.01/models/model.t7", map_location=self.device))
        self.model.to(self.device)
        self.model.eval()
        print(self.model)
        self.do_run = True
        self.data = []
        self.v = Visualizer()
        self.x = None
        self.y = None
        self.alpha = 0.5
    def __start_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.host, self.port))
            
    def __stop_socket(self):
        self.socket.close()
        
    def __test(self):
        dataset = WifiData(self.config, test = True)
        test_loader = DataLoader(dataset, batch_size=1)
        for data, _ in test_loader:
            data = data.to(self.device)
            
            logits = self.model(data)
            # print(data.shape, logits.shape)
            logits = logits.detach().numpy()[0]
            logits[0] = np.clip(logits[0], self.config.x_min, self.config.x_max)
            logits[1] = np.clip(logits[1], self.config.y_min, self.config.y_max)
            if not self.x:
                self.x = logits[0]
                self.y = logits[1]
            self.x = self.x * (1-self.alpha) + logits[0] * self.alpha
            self.y = self.y * (1-self.alpha) + logits[1] * self.alpha
            
            self.v.update(self.x, self.y)
            print(self.x, self.y)
            # self.v.update(logits[0], logits[1])
            # print(logits[0], logits[1])
            
    def start(self):
        self.__start_socket()
        t = threading.currentThread()
        while getattr(t, "do_run", True):
            datas = []
            for i in range(1):
                outdata = self.socket.recv(8192)
                # data = pickle.loads(data) #data loaded.
                try:
                    outdata = ast.literal_eval(outdata.decode())
                except:
                    print(len(outdata))
                    break
                data = {}
                for key, value in outdata.items():
                    outdata[key] = float(value) / 70
                data['Feature'] = outdata
                
                self.data.append(data)
                # print('Recieve a dict with length %d from %s' %(len(outdata), self.host))
                # Start testing
                datas.append(data)
            with open(self.path, 'wb') as fout:
                pickle.dump(datas, fout)
            self.__test()
            
        self.__stop_socket()

class TestClient():
    def __init__(self, config):
        self.config = config
        if not os.path.exists(config.root):
            os.makedirs(config.root)
        if not os.path.exists(config.root + config.test_path):
            os.makedirs(config.root + config.test_path)
        self.map_path = config.root + config.map_path
        datetime_dt = datetime.datetime.today()
        datetime_str = datetime_dt.strftime("%Y%m%d_%H%M%S")
        self.path = config.root + config.unlabeled_path + 'data' + datetime_str + '.json'
        self.__ClearData()
    def __ClearData(self):
        self.data = []
    def start(self):
        print('Start Testing')
        collectors = []
        for i, HOST in enumerate(self.config.hosts):
            collector = ClientThread(config=self.config, host=HOST, port=self.config.port)
            collectors.append(collector)
            collectors[i].start()
        stop = input('Type in anything to stop the program\n')
        for collector in collectors:
            collector.do_run = False
            collector.join()
            self.data = self.data + collector.data
    def SaveData(self):
        print('\nDump data to %s' %self.path)
        with open(self.path, 'wb') as fout:
            pickle.dump(self.data, fout)
        
if __name__ == '__main__':
    config = Config.from_json_file('config.json')
    testClient = ClientThread(config, host=config.hosts[0], port=8000)
    testClient.start()
    # testClient.SaveData()
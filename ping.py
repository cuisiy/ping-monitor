#!/bin/env python
# coding: utf-8
# create by cuisy at 2016/05/01

import os
import getpass
import sys
import json
import urllib2
import re
import socket
import time
import datetime
import ConfigParser
import threading
import Queue

def config():
    cf = ConfigParser.ConfigParser()
    confpath = os.path.split(os.path.realpath(__file__))[0]
    try:
        cf.read(confpath + "/ping.conf")
    except Exception, e:
        print e
        sys.exit(1)

    if cf.get("extends", "threadnum") != '' and 1 < int(cf.get("extends", "threadnum")) <=200:
        threadnum = int(cf.get("extends", "threadnum"))
    else:
        threadnum = 50

    if cf.get("extends", "time") != '' and 1 < int(cf.get("extends", "time")) <=59:
        runtime = int(cf.get("extends", "time"))
    else:
        runtime = 30

    if cf.get("extends", "step") != '' and int(cf.get("extends", "step")) % 30 == 0:
        step = int(cf.get("extends", "step"))
    else:
        step = 60

    if len(cf.items("base")) >= 1:
        mon_data = cf.items("base")
    else:
        print "no monitor items"
        sys.exit(1)

    if cf.get("extends", "push_falcon") != '' and int(cf.get("extends", "push_falcon")) == 1:
        push_falcon = 1
    else:
        push_falcon = 0

    if cf.get("extends", "logging") != '' and int(cf.get("extends", "logging")) == 1:
        logging = 1
    else:
        logging = 0

    return (mon_data,runtime,threadnum,step,push_falcon,logging)

def ping_status(thread_num, metric, hosts, runtime=10):
    value = {
                'loss_rate':0,
                'time_delay':0
            }
    cmd = 'ping -i 0.5 -c %i -n -q %s' % (int(runtime) * 2 - 1, hosts)
    data = os.popen(cmd).read()
    if 'packet loss' in data:
        loss_rate = int(data[data.find("received,") + len("received, "):data.find("% packet loss")])
        value['loss_rate'] = loss_rate
    if 'max' in data:
        time_delay = data[data.find("max/mdev = ") + len("max/mdev = "):data.find(" ms")].split("/")[1]
        value['time_delay'] = time_delay
    else:
        value['time_delay'] = 10000

    q.put((metric, hosts, value))

def push_data_to_falcon(hostname, ts, datas, step=60):
    payload = list()
    for i in range(len(datas)):
        for key, value in datas[i][2].items():
            tags = "%s=%s" % ("IP", datas[i][1])
            metric = "%s.%s.%s" % ("ping", key, datas[i][0])
            data = {"metric": metric,
                    "endpoint": hostname,
                    "timestamp": ts,
                    "step": step,
                    "value": value,
                    "counterType": "GAUGE",
                    "tags": tags}
            payload.append(data)
    #print json.dumps(payload)
    req = urllib2.Request("http://127.0.0.1:1988/v1/push", json.dumps(payload))
    response = urllib2.urlopen(req)

def log_recoard(datas):
    t = datetime.datetime.now()
    logpath = os.path.split(os.path.realpath(__file__))[0]  + "/logs"
    if not os.path.exists(logpath):
        os.makedirs(logpath)

    log_file = open(logpath + "/ping-monitor_" + t.strftime("%Y-%m-%d-%H")  + ".log", 'a')
    for i in range(len(datas)):
        outline = t.strftime("%Y/%m/%d %H:%M:%S") +  ' ' + str(datas[i]) + "\n"
        log_file.writelines(outline)
    log_file.close()

def main():
    conf = config()
    ts = int(time.time())
    hostname = socket.gethostname()
    threadpool = []
    ipformate = "[0-9]+\.[0-9]+\.[0-9]+\.[0-9]"
    (mon_data, runtime, threadnum, step, push_falcon, logging) = conf
    global q
    q = Queue.Queue()
    datas = list()
    for metric, ips in mon_data:
        for num, ip in enumerate(ips.split(',')):
            if re.match(ipformate, ip):
                th = threading.Thread(target = ping_status, args = (num, metric, ip, runtime))
                threadpool.append(th)
            else:
                print "host \"" + ip + "\" address is wrong, check format is x.x.x.x"

    if len(threadpool) > 0:
        for th in threadpool:
            th.start()
            while True:
                if (len(threading.enumerate()) <= threadnum):
                    break

        for th in threadpool:
            threading.Thread.join(th)

        while not q.empty():
            datas.append(q.get())
    else:
        sys.exit(1)

    if logging == 1:
        log_recoard(datas)

    if push_falcon == 1:
        push_data_to_falcon(hostname, ts, datas, step)
    else:
        for n in range(len(datas)):
            print datas[n]

if __name__ == '__main__':
    main()


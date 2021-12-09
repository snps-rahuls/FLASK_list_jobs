from flask import Flask,request
import time
import sys
from xml.etree import ElementTree as ET
import pandas as pd
import json
import xmltodict
import requests
import json
from sys import exit
import paramiko

def GetToken(Host, UserName, Password):
    url = "https://" + Host + "/api/v2/api-token-auth/"
    # print("url=", url)
    payload = json.dumps({
        "username": UserName,
        "password": Password
    })
    headers = {
        'Content-Type': 'application/json'
    }

    response = requests.request("POST", url, verify=False, headers=headers, data=payload)
    if response.status_code == 200:
        return response
    else:
        status=400
        return status

def GetResourceHandler(Host,Token):
    url = "https://" + Host + "/api/v2/environments/?attributes=name,id,resource_handler"
    payload = {}
    headers = Token
    response = requests.request("GET", url, verify=False, headers=headers, data=payload)
    if response.status_code ==200:
        return response
    else:
        status=400
        return status

def GetDetails(Host,Href,Token):
    # url="https://"+Host+"/api/v2/environments/ENV-g6po3ric/"
    url = "https://" + Host + Href
    payload = {}
    header = Token
    response1 = requests.request("GET", url,verify=False, headers=header, data=payload)
    if response1.status_code == 200:
        return response1
    else:
        status = 400
        return status

app = Flask(__name__)

@app.route("/")
def ssh():
    return "Home page"


@app.route('/list_jobs',methods=['POST'])
def ServerSSH():
    if request.method=='POST':
        data = request.get_json()
        if not data:
            # FarmName = 'abc'
            # subscription_name = 'abc'
            error = {"result":"body is empty"}
            return error
            exit()
        else:
            FarmName = data["FarmName"]
            SubscriptionName = data["subscription_name"]
            subscription_name = SubscriptionName
        # FarmName = 'tprj042'
        # subscription_name = 'Lightning Sandbox'
        Host = '172.17.8.4'
        UserName = 'svc-odcdevops'
        Password = 'Iltwas!23'
        tok = GetToken(Host, UserName, Password)
        if tok == 400:
            error = {"result": "token generation error"}
            return error
            exit()
        else:
            token = tok.text
            token1 = token[10:-2]
            Token = {'Authorization': 'Bearer {}'.format(token1)}

        resource_handler = GetResourceHandler(Host, Token)
        if resource_handler == 400:
            error = {"result": "resource handler error"}
            return error
            exit()
        else:
            data = json.loads(resource_handler.text)
            link = ''
            for d in data['_embedded']:
                if 'resource-handler' in d:
                    if d['resource-handler'] == subscription_name:
                        link = str(d['_links']['self']['href'])

        Href = str(link)
        if Href != '':
            GetDetails_response = GetDetails(Host, Href, Token)
            if GetDetails_response == 400:
                error = {"result": "get details error"}
                return error
                exit()
            else:
                res = json.loads(GetDetails_response.text)
                # print('res:',res)
                AD_Domain = ''
                AD_Server = ''
                Farm_Admin_Server = ''

                for d1 in res['parameters']:
                    # print("d1:", d1)
                    if d1['name'] == 'ad_domain':
                        AD_Domain = d1['options'][0]
                    if d1['name'] == 'ad_server_ip':
                        AD_Server = d1['options'][0]
                    if d1['name'] == 'farm_admin_server':
                        Farm_Admin_Server = d1['options'][0]
                print("AD_Serve:", AD_Server)
                print("AD_Domain:", AD_Domain)
                print("Farm_Admin_Server:", Farm_Admin_Server)
        else:
            error = {"result": "SubscriptionName is not correct!"}
            return error
            exit()
        print("Creating server Connection")
        ServerHost = Farm_Admin_Server
        USERNAME = 'saas_lightning_usr'
        PASSWORD = 'Iltwas!23'
        # connect to server
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ##port=22 by default
            ssh.connect(ServerHost, username=USERNAME, password=PASSWORD)
            print("server connection sucessfull")

        except Exception as e:
            error = "[!] Cannot connect to the SSH Server"
            return e, error
            exit()

        the_input1 = "source /remote/sge/default/" + FarmName + "/common/settings.sh;qstat -u '*' -ext -xml"
        the_input1 = the_input1.rstrip("\n")
        stdin, stdout, stderr = ssh.exec_command(the_input1)
        data = stdout.readlines()
        if len(data) != 0:
            stdin, stdout, stderr = ssh.exec_command(the_input1)
            cmdOutput = stdout.readlines()
            qstat_xml = "".join(cmdOutput)
            qstat_xml1 = ET.fromstring(qstat_xml.encode('utf-8'))
            oTypes = ['job_info', 'queue_info']
            l = []
            for oType in oTypes:
                for child in qstat_xml1.findall(oType):
                    for grandchild in child.findall('job_list'):
                        projectName = grandchild.find('JB_project').text
                        job_state1 = grandchild.find('state').text
                        if job_state1 == 'r':
                            job_state = 'running'
                        else:
                            job_state = 'pending'
                        user = grandchild.find('JB_owner').text
                        a = {"projectName": projectName, "user": user, "job_state": job_state}
                        l.append(a)
            all_proj = {}
            expected_data = {'jobsInfo': {}}
            for d in l:
                p_name = d['projectName']
                u_name = d['user']
                j_state = d['job_state']
                if j_state not in ("pending", "running"):
                    continue
                if p_name in all_proj:
                    if j_state in all_proj[p_name]['all']:
                        all_proj[p_name]['all'][j_state] += 1
                    else:
                        all_proj[p_name]['all'][j_state] = 1
                else:
                    all_proj[p_name] = {'all': {'pending': 0, 'running': 0}}
                    all_proj[p_name]['all'][j_state] = 1
                if u_name in all_proj[p_name]:
                    if j_state in all_proj[p_name][u_name]:
                        all_proj[p_name][u_name][j_state] += 1
                    else:
                        all_proj[p_name][u_name][j_state] = 1
                else:
                    all_proj[p_name][u_name] = {'pending': 0, 'running': 0}
                    all_proj[p_name][u_name][j_state] = 1
            for project in all_proj:
                expected_data['jobsInfo'][project] = all_proj[project]
            result=expected_data
            result1={"result":result}
            return result1

        else:
            print("error:", stderr.readline())
            error_msg = stderr.readlines()
            error_msg1 = {"result": "Farmname is not correct!"}
            ssh.close()
            return error_msg1

    else:
        error_msg1 = {"result": "Only POST method allowed"}
        return error_msg1


@app.route("/list_jobs1")
def ssh2():
    FarmName='tprj042'
    subscription_name = 'Lightning Sandbox'
    Host = '172.17.8.4'
    UserName = 'svc-odcdevops'
    Password = 'Iltwas!23'
    tok = GetToken(Host, UserName, Password)
    if tok == 400:
        print("connection error")
        print("status_error:", tok)
        exit()
    else:
        token = tok.text
        token1 = token[10:-2]
        Token = {'Authorization': 'Bearer {}'.format(token1)}

    resource_handler = GetResourceHandler(Host, Token)
    if resource_handler == 400:
        print("connection error")
        print("status_error:", resource_handler)
        exit()
    else:
        data = json.loads(resource_handler.text)
        link = ''
        for d in data['_embedded']:
            if 'resource-handler' in d:
                if d['resource-handler'] == subscription_name:
                    link = str(d['_links']['self']['href'])

    Href = str(link)
    if Href !='':
        GetDetails_response = GetDetails(Host, Href, Token)
        if GetDetails_response == 400:
            print("connection error")
            print("status_error:", GetDetails_response)
            exit()
        else:
            res = json.loads(GetDetails_response.text)
            # print('res:',res)
            AD_Domain = ''
            AD_Server = ''
            Farm_Admin_Server = ''

            for d1 in res['parameters']:
                # print("d1:", d1)
                if d1['name'] == 'ad_domain':
                    AD_Domain = d1['options'][0]
                if d1['name'] == 'ad_server_ip':
                    AD_Server = d1['options'][0]
                if d1['name'] == 'farm_admin_server':
                    Farm_Admin_Server = d1['options'][0]
    else:
        error="SubscriptionName is not correct!"
        return error
        exit()
    print("Creating server Connection")
    ServerHost = Farm_Admin_Server
    USERNAME = 'saas_lightning_usr'
    PASSWORD = 'Iltwas!23'
    # connect to server
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ##port=22 by default
        ssh.connect(ServerHost, username=USERNAME, password=PASSWORD)
        print("server connection sucessfull")

    except Exception as e:
        error   ="[!] Cannot connect to the SSH Server"
        return e,error
        exit()

    the_input1 = "source /remote/sge/default/" + FarmName + "/common/settings.sh;qstat -u '*' -ext -xml"
    the_input1 = the_input1.rstrip("\n")
    stdin, stdout, stderr = ssh.exec_command(the_input1)
    data = stdout.readlines()
    if len(data) != 0:
        stdin, stdout, stderr = ssh.exec_command(the_input1)
        cmdOutput = stdout.readlines()
        qstat_xml = "".join(cmdOutput)
        qstat_xml1 = ET.fromstring(qstat_xml.encode('utf-8'))
        # print("qsat_xml=",qstat_xml1)
        oTypes = ['job_info', 'queue_info']
        l = []
        for oType in oTypes:
            for child in qstat_xml1.findall(oType):
                for grandchild in child.findall('job_list'):
                    projectName = grandchild.find('JB_project').text
                    job_state1 = grandchild.find('state').text
                    if job_state1 == 'r':
                        job_state = 'running'
                    else:
                        job_state = 'pending'
                    user = grandchild.find('JB_owner').text
                    a = {"projectName": projectName, "user": user, "job_state": job_state}
                    l.append(a)
        all_proj = {}
        expected_data = {'jobsInfo': {}}
        for d in l:
            p_name = d['projectName']
            u_name = d['user']
            j_state = d['job_state']
            if j_state not in ("pending", "running"):
                continue
            if p_name in all_proj:
                if j_state in all_proj[p_name]['all']:
                    all_proj[p_name]['all'][j_state] += 1
                else:
                    all_proj[p_name]['all'][j_state] = 1
            else:
                all_proj[p_name] = {'all': {'pending': 0, 'running': 0}}
                all_proj[p_name]['all'][j_state] = 1
            if u_name in all_proj[p_name]:
                if j_state in all_proj[p_name][u_name]:
                    all_proj[p_name][u_name][j_state] += 1
                else:
                    all_proj[p_name][u_name][j_state] = 1
            else:
                all_proj[p_name][u_name] = {'pending': 0, 'running': 0}
                all_proj[p_name][u_name][j_state] = 1
        for project in all_proj:
            expected_data['jobsInfo'][project] = all_proj[project]

        result = expected_data
        result1 = {"result": result}
        return result1

    else:
        print("error:", stderr.readline())
        error_msg = stderr.readlines()
        error_msg1 = "Farmname is not correct!"
        ssh.close()
        return str(error_msg1)



@app.route('/list_jobs2',methods=['POST'])
def ServerSSH2():
    if request.method=='POST':
        FarmName = 'tprj042'
        subscription_name = 'Lightning Sandbox'
        Host = '172.17.8.4'
        UserName = 'svc-odcdevops'
        Password = 'Iltwas!23'
        tok = GetToken(Host, UserName, Password)
        if tok == 400:
            error = {"result": "token generation error"}
            return error
            exit()
        else:
            token = tok.text
            token1 = token[10:-2]
            Token = {'Authorization': 'Bearer {}'.format(token1)}

        resource_handler = GetResourceHandler(Host, Token)
        if resource_handler == 400:
            error = {"result": "resource handler error"}
            return error
            exit()
        else:
            data = json.loads(resource_handler.text)
            link = ''
            for d in data['_embedded']:
                if 'resource-handler' in d:
                    if d['resource-handler'] == subscription_name:
                        link = str(d['_links']['self']['href'])

        Href = str(link)
        if Href != '':
            GetDetails_response = GetDetails(Host, Href, Token)
            if GetDetails_response == 400:
                error = {"result": "get details error"}
                return error
                exit()
            else:
                res = json.loads(GetDetails_response.text)
                # print('res:',res)
                AD_Domain = ''
                AD_Server = ''
                Farm_Admin_Server = ''

                for d1 in res['parameters']:
                    # print("d1:", d1)
                    if d1['name'] == 'ad_domain':
                        AD_Domain = d1['options'][0]
                    if d1['name'] == 'ad_server_ip':
                        AD_Server = d1['options'][0]
                    if d1['name'] == 'farm_admin_server':
                        Farm_Admin_Server = d1['options'][0]
                print("AD_Serve:", AD_Server)
                print("AD_Domain:", AD_Domain)
                print("Farm_Admin_Server:", Farm_Admin_Server)
        else:
            error = {"result": "SubscriptionName is not correct!"}
            return error
            exit()
        print("Creating server Connection")
        ServerHost = Farm_Admin_Server
        USERNAME = 'saas_lightning_usr'
        PASSWORD = 'Iltwas!23'
        # connect to server
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ##port=22 by default
            ssh.connect(ServerHost, username=USERNAME, password=PASSWORD)
            print("server connection sucessfull")

        except Exception as e:
            error = "[!] Cannot connect to the SSH Server"
            return e, error
            exit()

        the_input1 = "source /remote/sge/default/" + FarmName + "/common/settings.sh;qstat -u '*' -ext -xml"
        the_input1 = the_input1.rstrip("\n")
        stdin, stdout, stderr = ssh.exec_command(the_input1)
        data = stdout.readlines()
        if len(data) != 0:
            stdin, stdout, stderr = ssh.exec_command(the_input1)
            cmdOutput = stdout.readlines()
            qstat_xml = "".join(cmdOutput)
            qstat_xml1 = ET.fromstring(qstat_xml.encode('utf-8'))
            oTypes = ['job_info', 'queue_info']
            l = []
            for oType in oTypes:
                for child in qstat_xml1.findall(oType):
                    for grandchild in child.findall('job_list'):
                        projectName = grandchild.find('JB_project').text
                        job_state1 = grandchild.find('state').text
                        if job_state1 == 'r':
                            job_state = 'running'
                        else:
                            job_state = 'pending'
                        user = grandchild.find('JB_owner').text
                        a = {"projectName": projectName, "user": user, "job_state": job_state}
                        l.append(a)
            all_proj = {}
            expected_data = {'jobsInfo': {}}
            for d in l:
                p_name = d['projectName']
                u_name = d['user']
                j_state = d['job_state']
                if j_state not in ("pending", "running"):
                    continue
                if p_name in all_proj:
                    if j_state in all_proj[p_name]['all']:
                        all_proj[p_name]['all'][j_state] += 1
                    else:
                        all_proj[p_name]['all'][j_state] = 1
                else:
                    all_proj[p_name] = {'all': {'pending': 0, 'running': 0}}
                    all_proj[p_name]['all'][j_state] = 1
                if u_name in all_proj[p_name]:
                    if j_state in all_proj[p_name][u_name]:
                        all_proj[p_name][u_name][j_state] += 1
                    else:
                        all_proj[p_name][u_name][j_state] = 1
                else:
                    all_proj[p_name][u_name] = {'pending': 0, 'running': 0}
                    all_proj[p_name][u_name][j_state] = 1
            for project in all_proj:
                expected_data['jobsInfo'][project] = all_proj[project]
            result=expected_data
            result1={"result":result}
            return result1

        else:
            print("error:", stderr.readline())
            error_msg = stderr.readlines()
            error_msg1 = {"result": "Farmname is not correct!"}
            ssh.close()
            return error_msg1
    else:
        error_msg = "Only POST method allowed"
        return str(error_msg)

if __name__ == "__main__":
    app.run(debug=True, port=8002)
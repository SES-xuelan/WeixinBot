#!/usr/bin/env python
# coding: utf-8
import qrcode
import urllib
import urllib2
import cookielib
import requests
import xml.dom.minidom
import json
import time
import re
import sys
import os
import random
import multiprocessing
import threading
import platform
import logging
from collections import defaultdict
from urlparse import urlparse
from lxml import html
from httplib import BadStatusLine
import HTMLParser

import sys

reload(sys)
sys.setdefaultencoding('utf-8')

# for media upload
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder


def catchKeyboardInterrupt(fn):
    def wrapper(*args):
        try:
            return fn(*args)
        except KeyboardInterrupt:
            print '\n[*] 强制退出程序'

    return wrapper


def _decode_list(data):
    rv = []
    for item in data:
        if isinstance(item, unicode):
            item = item.encode('utf-8')
        elif isinstance(item, list):
            item = _decode_list(item)
        elif isinstance(item, dict):
            item = _decode_dict(item)
        rv.append(item)
    return rv


def _decode_dict(data):
    rv = {}
    for key, value in data.iteritems():
        if isinstance(key, unicode):
            key = key.encode('utf-8')
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        elif isinstance(value, list):
            value = _decode_list(value)
        elif isinstance(value, dict):
            value = _decode_dict(value)
        rv[key] = value
    return rv


class WebWeixin(object):
    def __str__(self):
        description = \
            "=========================\n" + \
            "[#] Web Weixin\n" + \
            "[#] Debug Mode: " + str(self.DEBUG) + "\n" + \
            "[#] Uuid: " + self.uuid + "\n" + \
            "[#] Uin: " + str(self.uin) + "\n" + \
            "[#] Sid: " + self.sid + "\n" + \
            "[#] Skey: " + self.skey + "\n" + \
            "[#] DeviceId: " + self.deviceId + "\n" + \
            "[#] PassTicket: " + self.pass_ticket + "\n" + \
            "[#] Time: " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())) + "\n" + \
            "========================="
        return description

    def __init__(self):
        self.DEBUG = False
        self.uuid = ''
        self.base_uri = ''
        self.redirect_uri = ''
        self.uin = ''
        self.sid = ''
        self.skey = ''
        self.pass_ticket = ''
        self.deviceId = 'e' + repr(random.random())[2:17]
        self.BaseRequest = {}
        self.synckey = ''
        self.SyncKey = []
        self.User = []
        self.MemberList = []
        self.ContactList = []  # 好友
        self.GroupList = []  # 群
        self.GroupMemeberList = []  # 群友
        self.PublicUsersList = []  # 公众号／服务号
        self.SpecialUsersList = []  # 特殊账号
        self.autoReplyMode = False
        self.syncHost = ''
        self.user_agent = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'
        self.interactive = True
        self.autoOpen = False
        self.saveFolder = os.path.join(os.getcwd(), 'saved')
        self.saveSubFolders = {'webwxgeticon': 'icons', 'webwxgetheadimg': 'headimgs', 'webwxgetmsgimg': 'msgimgs',
                               'webwxgetvideo': 'videos', 'webwxgetvoice': 'voices', '_showQRCodeImg': 'qrcodes'}
        self.appid = 'wx782c26e4c19acffb'
        self.lang = 'zh_CN'
        self.lastCheckTs = time.time()
        self.memberCount = 0
        self.SpecialUsers = ['newsapp', 'fmessage', 'filehelper', 'weibo', 'qqmail', 'fmessage', 'tmessage', 'qmessage',
                             'qqsync', 'floatbottle', 'lbsapp', 'shakeapp', 'medianote', 'qqfriend', 'readerapp',
                             'blogapp', 'facebookapp', 'masssendapp', 'meishiapp', 'feedsapp',
                             'voip', 'blogappweixin', 'weixin', 'brandsessionholder', 'weixinreminder',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'officialaccounts', 'notification_messages',
                             'wxid_novlwrv3lqwv11', 'gh_22b87fa7cb3c', 'wxitil', 'userexperience_alarm',
                             'notification_messages']
        self.TimeOut = 20  # 同步最短时间间隔（单位：秒）
        self.media_count = -1
        self.AllMessages = {}

        self.cookie = cookielib.CookieJar()
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookie))
        opener.addheaders = [('User-agent', self.user_agent)]
        urllib2.install_opener(opener)

    def loadConfig(self, config):
        # 禁用 requests的log
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        if config['DEBUG']:
            self.DEBUG = config['DEBUG']
            if self.DEBUG == True:
                # 启用 requests的log
                logging.getLogger('requests').setLevel(logging.DEBUG)

        if config['autoReplyMode']:
            self.autoReplyMode = config['autoReplyMode']
        if config['user_agent']:
            self.user_agent = config['user_agent']
        if config['interactive']:
            self.interactive = config['interactive']
        if config['autoOpen']:
            self.autoOpen = config['autoOpen']

    def getUUID(self):
        url = 'https://login.weixin.qq.com/jslogin'
        params = {
            'appid': self.appid,
            'fun': 'new',
            'lang': self.lang,
            '_': int(time.time()),
        }
        data = self._post(url, params, False)
        regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
        pm = re.search(regx, data)
        if pm:
            code = pm.group(1)
            self.uuid = pm.group(2)
            return code == '200'
        return False

    def genQRCode(self):
        if sys.platform.startswith('win'):
            self._showQRCodeImg()
        else:
            self._str2qr('https://login.weixin.qq.com/l/' + self.uuid)

    def _showQRCodeImg(self):
        url = 'https://login.weixin.qq.com/qrcode/' + self.uuid
        params = {
            't': 'webwx',
            '_': int(time.time())
        }

        data = self._post(url, params, False)
        QRCODE_PATH = self._saveFile('qrcode.jpg', data, '_showQRCodeImg')
        os.startfile(QRCODE_PATH)

    def waitForLogin(self, tip=1):
        time.sleep(tip)
        url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
            tip, self.uuid, int(time.time()))
        data = self._get(url)
        pm = re.search(r'window.code=(\d+);', data)
        code = pm.group(1)

        if code == '201':
            return True
        elif code == '200':
            pm = re.search(r'window.redirect_uri="(\S+?)";', data)
            r_uri = pm.group(1) + '&fun=new'
            self.redirect_uri = r_uri
            self.base_uri = r_uri[:r_uri.rfind('/')]
            return True
        elif code == '408':
            self._echo('[登陆超时] \n')
        else:
            self._echo('[登陆异常] \n')
        return False

    def login(self):
        data = self._get(self.redirect_uri)
        doc = xml.dom.minidom.parseString(data)
        root = doc.documentElement

        for node in root.childNodes:
            if node.nodeName == 'skey':
                self.skey = node.childNodes[0].data
            elif node.nodeName == 'wxsid':
                self.sid = node.childNodes[0].data
            elif node.nodeName == 'wxuin':
                self.uin = node.childNodes[0].data
            elif node.nodeName == 'pass_ticket':
                self.pass_ticket = node.childNodes[0].data

        if '' in (self.skey, self.sid, self.uin, self.pass_ticket):
            return False

        self.BaseRequest = {
            'Uin': int(self.uin),
            'Sid': self.sid,
            'Skey': self.skey,
            'DeviceID': self.deviceId,
        }
        return True

    def webwxinit(self):
        url = self.base_uri + '/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        params = {
            'BaseRequest': self.BaseRequest
        }
        dic = self._post(url, params)
        self.SyncKey = dic['SyncKey']
        self.User = dic['User']
        # synckey for synccheck
        self.synckey = '|'.join(
            [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])

        return dic['BaseResponse']['Ret'] == 0

    def webwxstatusnotify(self):
        url = self.base_uri + \
              '/webwxstatusnotify?lang=zh_CN&pass_ticket=%s' % (self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Code": 3,
            "FromUserName": self.User['UserName'],
            "ToUserName": self.User['UserName'],
            "ClientMsgId": int(time.time())
        }
        dic = self._post(url, params)

        return dic['BaseResponse']['Ret'] == 0

    def webwxgetcontact(self):
        SpecialUsers = self.SpecialUsers
        print self.base_uri
        url = self.base_uri + '/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
            self.pass_ticket, self.skey, int(time.time()))
        dic = self._post(url, {})

        self.MemberCount = dic['MemberCount']
        self.MemberList = dic['MemberList']
        ContactList = self.MemberList[:]
        GroupList = self.GroupList[:]
        PublicUsersList = self.PublicUsersList[:]
        SpecialUsersList = self.SpecialUsersList[:]

        for i in xrange(len(ContactList) - 1, -1, -1):
            Contact = ContactList[i]
            if Contact['VerifyFlag'] & 8 != 0:  # 公众号/服务号
                ContactList.remove(Contact)
                self.PublicUsersList.append(Contact)
            elif Contact['UserName'] in SpecialUsers:  # 特殊账号
                ContactList.remove(Contact)
                self.SpecialUsersList.append(Contact)
            elif Contact['UserName'].find('@@') != -1:  # 群聊
                ContactList.remove(Contact)
                self.GroupList.append(Contact)
            elif Contact['UserName'] == self.User['UserName']:  # 自己
                ContactList.remove(Contact)
        self.ContactList = ContactList

        return True

    def webwxbatchgetcontact(self):
        url = self.base_uri + \
              '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (
                  int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": len(self.GroupList),
            "List": [{"UserName": g['UserName'], "EncryChatRoomId": ""} for g in self.GroupList]
        }
        dic = self._post(url, params)

        # blabla ...
        ContactList = dic['ContactList']
        ContactCount = dic['Count']
        self.GroupList = ContactList

        for i in xrange(len(ContactList) - 1, -1, -1):
            Contact = ContactList[i]
            MemberList = Contact['MemberList']
            for member in MemberList:
                self.GroupMemeberList.append(member)
        return True

    def getNameById(self, id):
        url = self.base_uri + \
              '/webwxbatchgetcontact?type=ex&r=%s&pass_ticket=%s' % (
                  int(time.time()), self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            "Count": 1,
            "List": [{"UserName": id, "EncryChatRoomId": ""}]
        }
        dic = self._post(url, params)

        # blabla ...
        return dic['ContactList']

    def testsynccheck(self):
        SyncHost = [
            'webpush.wx.qq.com',
            'webpush.weixin.qq.com',
            'webpush2.weixin.qq.com',
            'webpush.wechat.com',
            'webpush1.wechat.com',
            'webpush2.wechat.com',
            'webpush.web.wechat.com',
            # 'webpush.wechatapp.com'
        ]
        for host in SyncHost:
            self.syncHost = host
            [retcode, selector] = self.synccheck()
            print(retcode + '|' + selector + '|' + host)
            if retcode == '0':
                return True
        return False

    def synccheck(self):
        params = {
            'r': int(time.time()),
            'sid': self.sid,
            'uin': self.uin,
            'skey': self.skey,
            'deviceid': self.deviceId,
            'synckey': self.synckey,
            '_': int(time.time()),
        }
        url = 'https://' + self.syncHost + '/cgi-bin/mmwebwx-bin/synccheck?' + urllib.urlencode(params)
        data = self._get(url)
        # print 'data:' + data
        pm = re.search(
            r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}', data)
        retcode = pm.group(1)
        selector = pm.group(2)
        return [retcode, selector]

    def webwxsync(self):
        url = self.base_uri + \
              '/webwxsync?sid=%s&skey=%s&pass_ticket=%s' % (
                  self.sid, self.skey, self.pass_ticket)
        params = {
            'BaseRequest': self.BaseRequest,
            'SyncKey': self.SyncKey,
            'rr': ~int(time.time())
        }
        dic = self._post(url, params)
        if self.DEBUG:
            print json.dumps(dic, indent=4)
            self._log(json.dumps(dic, indent=4))

        if dic['BaseResponse']['Ret'] == 0:
            self.SyncKey = dic['SyncKey']
            self.synckey = '|'.join(
                [str(keyVal['Key']) + '_' + str(keyVal['Val']) for keyVal in self.SyncKey['List']])
        return dic

    def webwxsendmsg(self, word, to='filehelper'):
        url = self.base_uri + \
              '/webwxsendmsg?pass_ticket=%s' % (self.pass_ticket)
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        params = {
            'BaseRequest': self.BaseRequest,
            'Msg': {
                "Type": 1,
                "Content": self._transcoding(word),
                "FromUserName": self.User['UserName'],
                "ToUserName": to,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(params, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxuploadmedia(self, image_name):
        url = 'https://file2.wx.qq.com/cgi-bin/mmwebwx-bin/webwxuploadmedia?f=json'
        # 计数器
        self.media_count = self.media_count + 1
        # 文件名
        file_name = image_name
        # MIME格式
        # mime_type = application/pdf, image/jpeg, image/png, etc.
        mime_type = mimetypes.guess_type(image_name, strict=False)[0]
        # 微信识别的文档格式，微信服务器应该只支持两种类型的格式。pic和doc
        # pic格式，直接显示。doc格式则显示为文件。
        media_type = 'pic' if mime_type.split('/')[0] == 'image' else 'doc'
        # 上一次修改日期
        lastModifieDate = 'Thu Mar 17 2016 00:55:10 GMT+0800 (CST)'
        # 文件大小
        file_size = os.path.getsize(file_name)
        # PassTicket
        pass_ticket = self.pass_ticket
        # clientMediaId
        client_media_id = str(int(time.time() * 1000)) + \
                          str(random.random())[:5].replace('.', '')
        # webwx_data_ticket
        webwx_data_ticket = ''
        for item in self.cookie:
            if item.name == 'webwx_data_ticket':
                webwx_data_ticket = item.value
                break
        if (webwx_data_ticket == ''):
            return "None Fuck Cookie"

        uploadmediarequest = json.dumps({
            "BaseRequest": self.BaseRequest,
            "ClientMediaId": client_media_id,
            "TotalLen": file_size,
            "StartPos": 0,
            "DataLen": file_size,
            "MediaType": 4
        }, ensure_ascii=False).encode('utf8')

        multipart_encoder = MultipartEncoder(
            fields={
                'id': 'WU_FILE_' + str(self.media_count),
                'name': file_name,
                'type': mime_type,
                'lastModifieDate': lastModifieDate,
                'size': str(file_size),
                'mediatype': media_type,
                'uploadmediarequest': uploadmediarequest,
                'webwx_data_ticket': webwx_data_ticket,
                'pass_ticket': pass_ticket,
                'filename': (file_name, open(file_name, 'rb'), mime_type.split('/')[1])
            },
            boundary='-----------------------------1575017231431605357584454111'
        )

        headers = {
            'Host': 'file2.wx.qq.com',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:42.0) Gecko/20100101 Firefox/42.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://wx2.qq.com/',
            'Content-Type': multipart_encoder.content_type,
            'Origin': 'https://wx2.qq.com',
            'Connection': 'keep-alive',
            'Pragma': 'no-cache',
            'Cache-Control': 'no-cache'
        }

        r = requests.post(url, data=multipart_encoder, headers=headers)
        response_json = r.json()
        if response_json['BaseResponse']['Ret'] == 0:
            return response_json
        return None

    def webwxsendmsgimg(self, user_id, media_id):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendmsgimg?fun=async&f=json&pass_ticket=%s' % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 3,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        return dic['BaseResponse']['Ret'] == 0

    def webwxsendmsgemotion(self, user_id, media_id):
        url = 'https://wx2.qq.com/cgi-bin/mmwebwx-bin/webwxsendemoticon?fun=sys&f=json&pass_ticket=%s' % self.pass_ticket
        clientMsgId = str(int(time.time() * 1000)) + \
                      str(random.random())[:5].replace('.', '')
        data_json = {
            "BaseRequest": self.BaseRequest,
            "Msg": {
                "Type": 47,
                "EmojiFlag": 2,
                "MediaId": media_id,
                "FromUserName": self.User['UserName'],
                "ToUserName": user_id,
                "LocalID": clientMsgId,
                "ClientMsgId": clientMsgId
            }
        }
        headers = {'content-type': 'application/json; charset=UTF-8'}
        data = json.dumps(data_json, ensure_ascii=False).encode('utf8')
        r = requests.post(url, data=data, headers=headers)
        dic = r.json()
        if self.DEBUG:
            print json.dumps(dic, indent=4)
            self._log(json.dumps(dic, indent=4))
        return dic['BaseResponse']['Ret'] == 0

    def _saveFile(self, filename, data, api=None):
        fn = filename
        if self.saveSubFolders[api]:
            dirName = os.path.join(self.saveFolder, self.saveSubFolders[api])
            if not os.path.exists(dirName):
                os.makedirs(dirName)
            fn = os.path.join(dirName, filename)
            self._log('Saved file: %s' % fn)
            with open(fn, 'wb') as f:
                f.write(data)
                f.close()
        return fn

    def webwxgeticon(self, id):
        url = self.base_uri + \
              '/webwxgeticon?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgeticon')

    def webwxgetheadimg(self, id):
        url = self.base_uri + \
              '/webwxgetheadimg?username=%s&skey=%s' % (id, self.skey)
        data = self._get(url)
        fn = 'img_' + id + '.jpg'
        return self._saveFile(fn, data, 'webwxgetheadimg')

    def webwxgetmsgimg(self, msgid):
        url = self.base_uri + \
              '/webwxgetmsgimg?MsgID=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        fn = 'img_' + msgid + '.jpg'
        return self._saveFile(fn, data, 'webwxgetmsgimg')

    # Not work now for weixin haven't support this API
    def webwxgetvideo(self, msgid):
        url = self.base_uri + \
              '/webwxgetvideo?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url, api='webwxgetvideo')
        fn = 'video_' + msgid + '.mp4'
        return self._saveFile(fn, data, 'webwxgetvideo')

    def webwxgetvoice(self, msgid):
        url = self.base_uri + \
              '/webwxgetvoice?msgid=%s&skey=%s' % (msgid, self.skey)
        data = self._get(url)
        fn = 'voice_' + msgid + '.mp3'
        return self._saveFile(fn, data, 'webwxgetvoice')

    def getGroupName(self, id):
        name = '未知群'
        for member in self.GroupList:
            if member['UserName'] == id:
                name = member['NickName']
        if name == '未知群':
            # 现有群里面查不到
            GroupList = self.getNameById(id)
            for group in GroupList:
                self.GroupList.append(group)
                if group['UserName'] == id:
                    name = group['NickName']
                    MemberList = group['MemberList']
                    for member in MemberList:
                        self.GroupMemeberList.append(member)
        return name

    def getUserRemarkName(self, id):
        name = '未知群' if id[:2] == '@@' else '陌生人'
        if id == self.User['UserName']:
            return self.User['NickName']  # 自己

        if id[:2] == '@@':
            # 群
            name = self.getGroupName(id)
        else:
            # 特殊账号
            for member in self.SpecialUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 公众号或服务号
            for member in self.PublicUsersList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']

            # 直接联系人
            for member in self.ContactList:
                if member['UserName'] == id:
                    name = member['RemarkName'] if member[
                        'RemarkName'] else member['NickName']
            # 群友
            for member in self.GroupMemeberList:
                if member['UserName'] == id:
                    name = member['DisplayName'] if member[
                        'DisplayName'] else member['NickName']

        if name == '未知群' or name == '陌生人':
            self._log(id)
        return name

    def getUSerID(self, name):
        for member in self.MemberList:
            if name == member['RemarkName'] or name == member['NickName']:
                return member['UserName']
        return None

    def getGroupID(self, name):
        for group in self.GroupList:
            if name == group['NickName']:
                return group['UserName']
        return None

    def _showMsg(self, message):

        srcName = None
        dstName = None
        groupName = None
        content = None
        message_id = ''
        msg = message
        self._log(msg)

        if msg['raw_msg']:
            srcName = self.getUserRemarkName(msg['raw_msg']['FromUserName'])
            dstName = self.getUserRemarkName(msg['raw_msg']['ToUserName'])
            content = msg['raw_msg']['Content'].replace(
                '&lt;', '<').replace('&gt;', '>')
            message_id = msg['raw_msg']['MsgId']

            if content.find('http://weixin.qq.com/cgi-bin/redirectforward?args=') != -1:
                # 地理位置消息
                data = self._get(content).decode('gbk').encode('utf-8')
                pos = self._searchContent('title', data, 'xml')
                tree = html.fromstring(self._get(content))
                url = tree.xpath('//html/body/div/img')[0].attrib['src']

                for item in urlparse(url).query.split('&'):
                    if item.split('=')[0] == 'center':
                        loc = item.split('=')[-1:]

                content = '%s 发送了一个 位置消息 - 我在 [%s](%s) @ %s]' % (
                    srcName, pos, url, loc)

            if msg['raw_msg']['ToUserName'] == 'filehelper':
                # 文件传输助手
                dstName = '文件传输助手'

            if msg['raw_msg']['FromUserName'][:2] == '@@':
                # 接收到来自群的消息
                if re.search(":<br/>", content, re.IGNORECASE):
                    [people, content] = content.split(':<br/>', 1)
                    groupName = srcName
                    srcName = self.getUserRemarkName(people)
                    dstName = 'GROUP'
                else:
                    groupName = srcName
                    srcName = 'SYSTEM'
            elif msg['raw_msg']['ToUserName'][:2] == '@@':
                # 自己发给群的消息
                groupName = dstName
                dstName = 'GROUP'

            # 收到了红包
            if content == '收到红包，请在手机上查看':
                msg['message'] = content
                if self.webwxsendmsg('抢红包啦！！！', msg['raw_msg']['FromUserName']):
                    print '抢红包啦！！！'
                else:
                    print '发送信息失败'
                    self._info('发送信息失败')

            # 指定了消息内容
            if 'message' in msg.keys():
                content = msg['message']

        fnContent = ''

        if groupName != None:
            fnContent = '%s |%s| %s -> %s: %s' % (message_id, groupName.strip(),
                                                  srcName.strip(), dstName.strip(), content.replace('<br/>', '\n'))
        else:
            fnContent = '%s %s -> %s: %s' % (message_id, srcName.strip(),
                                             dstName.strip(), content.replace('<br/>', '\n'))

        print fnContent

        self.AllMessages[str(message_id)] = content
        self._info(fnContent)

        fn = 'msgs/msg.json'
        with open(fn, 'a') as f:
            f.write(fnContent + '\n\n')

    def handleMsg(self, r):
        for msg in r['AddMsgList']:
            # print '[*] 你有新的消息，请注意查收'
            # self._log('[*] 你有新的消息，请注意查收')

            if self.DEBUG:
                print '[*] 该消息已储存到文件: ' + fn
                self._log('[*] 该消息已储存到文件: %s' % (fn))

            msgType = msg['MsgType']
            name = self.getUserRemarkName(msg['FromUserName'])
            content = msg['Content'].replace('&lt;', '<').replace('&gt;', '>')
            msgid = msg['MsgId']

            if msgType == 1:
                raw_msg = {'raw_msg': msg}
                self._showMsg(raw_msg)
                # print '###' + str(content.find('小精灵')) + '###' + str(
                #     content.find('@' + self.User['NickName']))
                nick = content.find('@' + self.User['NickName'])
                xiaojngling = content.find('小精灵')
                dva = content.find('喵咪D.VA')
                if xiaojngling > 0 or nick > 0 or dva > 0:
                    if xiaojngling > 0:
                        content = content[xiaojngling + len('小精灵'):]
                    elif nick > 0:
                        content = content[nick + len('@' + self.User['NickName']):]
                    elif dva > 0:
                        content = content[dva + len('喵咪D.VA'):]

                    ans = self._xiaojingling_post(content)
                    self._autoReply(ans, msg['FromUserName'])
                elif msg['FromUserName'][:2] != '@@' and msg['FromUserName'] != self.User['UserName']:
                    ans = '[自动回复]您好，我现在有事不在，一会再和您联系，如果有急事请打电话'

                    is_pub = False
                    # 公众号或服务号 不自动回复
                    for member in self.PublicUsersList:
                        if member['UserName'] == msg['FromUserName']:
                            is_pub = True
                            break
                    if not is_pub:
                        self._autoReply(ans, msg['FromUserName'])


            elif msgType == 3:
                image = self.webwxgetmsgimg(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发送了一张图片: %s' % (name, image)}
                self._showMsg(raw_msg)
                self._safe_open(image)
                if msg['FromUserName'][:2] != '@@':
                    ans = '[自动回复]您好，我现在有事不在，一会再和您联系，如果有急事请打电话'
                    self._autoReply(ans, msg['FromUserName'])

            elif msgType == 34:
                voice = self.webwxgetvoice(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段语音: %s' % (name, voice)}
                self._showMsg(raw_msg)
                self._safe_open(voice)
                if msg['FromUserName'][:2] != '@@':
                    self._autoReply('[自动回复]您好，我现在有事不在，听不了语音，稍后再和您联系，如果有急事请打电话', msg['FromUserName'])

            elif msgType == 42:
                info = msg['RecommendInfo']
                print '%s 发送了一张名片:' % name
                print '========================='
                print '= 昵称: %s' % info['NickName']
                print '= 微信号: %s' % info['Alias']
                print '= 地区: %s %s' % (info['Province'], info['City'])
                print '= 性别: %s' % ['未知', '男', '女'][info['Sex']]
                print '========================='
                raw_msg = {'raw_msg': msg, 'message': '%s 发送了一张名片: %s' % (
                    name.strip(), json.dumps(info))}
                self._showMsg(raw_msg)
            elif msgType == 47:
                url = self._searchContent('cdnurl', content)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一个动画表情，点击下面链接查看: %s' % (name, url)}
                self._showMsg(raw_msg)
                self._safe_open(url)
                if msg['FromUserName'][:2] != '@@':
                    self._autoReply('[自动回复]您好，我现在有事不在，看不了表情，一会再和您联系，如果有急事请打电话', msg['FromUserName'])

            elif msgType == 49:

                html_parser = HTMLParser.HTMLParser()
                appMsgType = defaultdict(lambda: "")
                appMsgType.update({5: '链接', 3: '音乐', 7: '微博'})
                print '%s 分享了一个%s:' % (name, appMsgType[msg['AppMsgType']])
                print '========================='
                print '= 标题: %s' % msg['FileName']
                print '= 描述: %s' % self._searchContent('des', content, 'xml')
                print '= 链接: %s' % html_parser.unescape(msg['Url'])
                print '= 来自: %s' % self._searchContent('appname', content, 'xml')
                print '========================='
                card = {
                    'title': msg['FileName'],
                    'description': self._searchContent('des', content, 'xml'),
                    'url': msg['Url'],
                    'appname': self._searchContent('appname', content, 'xml')
                }
                raw_msg = {'raw_msg': msg, 'message': '%s 分享了一个%s: %s' % (
                    name, appMsgType[msg['AppMsgType']], json.dumps(card))}
                self._showMsg(raw_msg)
            elif msgType == 51:
                # raw_msg = {'raw_msg': msg, 'message': '[*] 成功获取联系人信息'}
                # self._showMsg(raw_msg)
                self._log(msg)
            elif msgType == 62:
                video = self.webwxgetvideo(msgid)
                raw_msg = {'raw_msg': msg,
                           'message': '%s 发了一段小视频: %s' % (name, video)}
                self._showMsg(raw_msg)
                self._safe_open(video)
                if msg['FromUserName'][:2] != '@@':
                    self._autoReply('[自动回复]您好，我现在有事不在，稍后再看你发的小视频哈，如果有急事请打电话', msg['FromUserName'])

            elif msgType == 10002:
                raw_msg = {'raw_msg': msg, 'message': '%s 撤回了一条消息' % name}
                # print "msg:" + str(msg)
                self._showMsg(raw_msg)
                srcName = name
                if msg['FromUserName'][:2] == '@@':
                    # 来自群的消息
                    if re.search(":<br/>", content, re.IGNORECASE):
                        [people, content] = content.split(':<br/>', 1)
                        srcName = self.getUserRemarkName(people)
                    else:
                        srcName = ""

                self._autoReply('天啦噜~ %s 又撤回了一条消息' % srcName, msg['FromUserName'])

                oldmsgid = re.search('<msgid>(\d+)</msgid>', content)
                # print("oldmsgid:" + str(oldmsgid.group(1)))
                fnContent = '撤回的消息 id：' + oldmsgid.group(1) + "|谁撤回的：" + srcName + "|内容：" + self.AllMessages[
                    str(oldmsgid.group(1))]
                print (fnContent)

                fn = 'msgs/undo.json'
                with open(fn, 'a') as f:
                    # f.write(fnContent + "|full_message:" + str(msg) + '\n\n')
                    f.write(fnContent + '\n\n')

            else:
                self._log('[*] 该消息类型为: %d，可能是表情，图片, 链接或红包: %s' %
                          (msg['MsgType'], json.dumps(msg)))
                raw_msg = {
                    'raw_msg': msg, 'message': '[*] 该消息类型为: %d，可能是表情，图片, 链接或红包' % msg['MsgType']}
                self._showMsg(raw_msg)

                # print("self.AllMessages:" + str(self.AllMessages))

    def listenMsgMode(self):
        print '[*] 进入消息监听模式 ... 成功'
        self._log('[*] 进入消息监听模式 ... 成功')
        self._run('[*] 进行同步线路测试 ... ', self.testsynccheck)
        playWeChat = 0
        redEnvelope = 0
        while True:
            self.lastCheckTs = time.time()
            [retcode, selector] = self.synccheck()
            if self.DEBUG:
                print 'retcode: %s, selector: %s' % (retcode, selector)
            self._log('retcode: %s, selector: %s' % (retcode, selector))
            if retcode == '1100':
                print '[*] 你在手机上登出了微信，债见'
                self._log('[*] 你在手机上登出了微信，债见')
                break
            if retcode == '1101':
                print '[*] 你在其他地方登录了 WEB 版微信，债见'
                self._log('[*] 你在其他地方登录了 WEB 版微信，债见')
                break
            elif retcode == '0':
                if selector == '2':
                    r = self.webwxsync()
                    if r is not None:
                        self.handleMsg(r)
                elif selector == '6':
                    # TODO
                    redEnvelope += 1
                    print '[*] 收到疑似红包消息 %d 次' % redEnvelope
                    self._log('[*] 收到疑似红包消息 %d 次' % redEnvelope)
                    r = self.webwxsync()
                    if r is not None:
                        self.handleMsg(r)
                elif selector == '7':
                    playWeChat += 1
                    print '[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat
                    self._log('[*] 你在手机上玩微信被我发现了 %d 次' % playWeChat)
                    r = self.webwxsync()
                elif selector == '0':
                    time.sleep(1)
            if (time.time() - self.lastCheckTs) <= 20:
                time.sleep(time.time() - self.lastCheckTs)

    def sendMsg(self, name, word, isfile=False):
        id = self.getUSerID(name)
        if id == None:
            id = self.getGroupID(name)

        self._log(name)
        if id:
            if isfile:
                with open(word, 'r') as f:
                    for line in f.readlines():
                        line = line.replace('\n', '')
                        self._echo('-> ' + name + ': ' + line)
                        if self.webwxsendmsg(line, id):
                            print ' [成功]'
                        else:
                            print ' [失败]'
                        time.sleep(1)
            else:
                if self.webwxsendmsg(word, id):
                    print '[*] 消息发送成功'
                    self._log('[*] 消息发送成功')
                else:
                    print '[*] 消息发送失败'
                    self._log('[*] 消息发送失败')
        else:
            print '[*] 此用户不存在'
            self._log('[*] 此用户不存在')

    def sendMsgToAll(self, word):
        for contact in self.ContactList:
            name = contact['RemarkName'] if contact[
                'RemarkName'] else contact['NickName']
            id = contact['UserName']
            self._echo('-> ' + name + ': ' + word)
            if self.webwxsendmsg(word, id):
                print ' [成功]'
            else:
                print ' [失败]'
            time.sleep(1)

    def sendImg(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgimg(user_id, media_id)

    def sendEmotion(self, name, file_name):
        response = self.webwxuploadmedia(file_name)
        media_id = ""
        if response is not None:
            media_id = response['MediaId']
        user_id = self.getUSerID(name)
        response = self.webwxsendmsgemotion(user_id, media_id)

    @catchKeyboardInterrupt
    def start(self):
        self._echo('[*] 微信网页版 ... 开动')
        print
        self._log('[*] 微信网页版 ... 开动')
        while True:
            self._run('[*] 正在获取 uuid ... ', self.getUUID)
            self._echo('[*] 正在获取二维码 ... 成功')
            print
            self._log('[*] 微信网页版 ... 开动')
            self.genQRCode()
            print '[*] 请使用微信扫描二维码以登录 ... '
            if not self.waitForLogin():
                continue
                print '[*] 请在手机上点击确认以登录 ... '
            if not self.waitForLogin(0):
                continue
            break

        self._run('[*] 正在登录 ... ', self.login)
        self._run('[*] 微信初始化 ... ', self.webwxinit)
        self._run('[*] 开启状态通知 ... ', self.webwxstatusnotify)
        self._run('[*] 获取联系人 ... ', self.webwxgetcontact)
        self._echo('[*] 应有 %s 个联系人，读取到联系人 %d 个' %
                   (self.MemberCount, len(self.MemberList)))
        print
        self._echo('[*] 共有 %d 个群 | %d 个直接联系人 | %d 个特殊账号 ｜ %d 公众号或服务号' % (len(self.GroupList),
                                                                         len(self.ContactList),
                                                                         len(self.SpecialUsersList),
                                                                         len(self.PublicUsersList)))
        print
        self._run('[*] 获取群 ... ', self.webwxbatchgetcontact)
        self._log('[*] 微信网页版 ... 开动')
        if self.DEBUG:
            print self
            self._log(self)

        # if self.interactive and raw_input('[*] 是否开启自动回复模式(y/n): ') == 'y':
        if self.interactive:
            self.autoReplyMode = "1"
            print '[*] 自动回复模式 ... 开启'
            self._log('[*] 自动回复模式 ... 开启')
        else:
            print '[*] 自动回复模式 ... 关闭'
            self._log('[*] 自动回复模式 ... 关闭')

        self._switchautoReplyMode(self.autoReplyMode)
        listenProcess = multiprocessing.Process(target=self.listenMsgMode)
        # listenProcess = threading.Thread(target=self.listenMsgMode)
        listenProcess.start()

        while True:
            text = raw_input('')
            if text == 'quit':
                listenProcess.terminate()
                print('[*] 退出微信')
                self._log('[*] 退出微信')
                exit()
            elif text[:2] == '->':
                [name, word] = text[2:].split(':', 1)
                if name == 'all':
                    self.sendMsgToAll(word)
                else:
                    self.sendMsg(name, word)
            elif text[:3] == 'm->':
                [name, file] = text[3:].split(':', 1)
                self.sendMsg(name, file, True)
            elif text[:3] == 'f->':
                print '发送文件'
                self._log('发送文件')
            elif text[:3] == 'i->':
                print '发送图片'
                [name, file_name] = text[3:].split(':', 1)
                self.sendImg(name, file_name)
                self._log('发送图片')
            elif text[:3] == 'e->':
                print '发送表情'
                [name, file_name] = text[3:].split(':', 1)
                self.sendEmotion(name, file_name)
                self._log('发送表情')
            elif text == 'autorep0':
                print '开启自动回复 0 【回复群组和个人】'
                self._switchautoReplyMode("0")
            elif text == 'autorep1':
                print '开启自动回复 1【仅回复群组】'
                self._switchautoReplyMode("1")
            elif text == 'autorep2':
                print '开启自动回复 2【仅回复个人】'
                self._switchautoReplyMode("2")
            elif text == 'autorepoff':
                print '关闭自动回复'
                self._switchautoReplyMode("-1")

    def _safe_open(self, path):
        if self.autoOpen:
            if platform.system() == "Linux":
                os.system("xdg-open %s &" % path)
            else:
                os.system('open %s &' % path)

    def _run(self, str, func, *args):
        self._echo(str)
        if func(*args):
            print '成功'
            self._log('%s... 成功' % (str))
        else:
            print('失败\n[*] 退出程序')
            self._log('%s... 失败' % (str))
            self._log('[*] 退出程序')
            exit()

    def _echo(self, str):
        sys.stdout.write(str)
        sys.stdout.flush()

    def _printQR(self, mat):
        for i in mat:
            BLACK = '\033[40m  \033[0m'
            WHITE = '\033[47m  \033[0m'
            print ''.join([BLACK if j else WHITE for j in i])

    def _str2qr(self, str):
        qr = qrcode.QRCode()
        qr.border = 1
        qr.add_data(str)
        mat = qr.get_matrix()
        self._printQR(mat)  # qr.print_tty() or qr.print_ascii()

    def _transcoding(self, data):
        if not data:
            return data
        result = None
        if type(data) == unicode:
            result = data
        elif type(data) == str:
            result = data.decode('utf-8')
        return result

    def _get(self, url, api=None):
        request = urllib2.Request(url=url)
        request.add_header('Referer', 'https://wx.qq.com/')
        if api == 'webwxgetvoice':
            request.add_header('Range', 'bytes=0-')
        if api == 'webwxgetvideo':
            request.add_header('Range', 'bytes=0-')

        try:
            response = urllib2.urlopen(request)
            data = response.read()
            self._log(url)
            return data
        except BadStatusLine:
            # 出错了，返回 retcode:0,selector:0 假装没出错 ^_^
            # print "could not fetch %s" % url
            return "window.synccheck={retcode:\"0\",selector:\"0\"}"

    def _post(self, url, params, jsonfmt=True):
        if jsonfmt:
            request = urllib2.Request(url=url, data=json.dumps(params))
            request.add_header(
                'ContentType', 'application/json; charset=UTF-8')
        else:
            request = urllib2.Request(url=url, data=urllib.urlencode(params))
        response = urllib2.urlopen(request)
        data = response.read()
        if jsonfmt:
            return json.loads(data, object_hook=_decode_dict)
        return data

    def _xiaodoubi(self, word):
        url = 'http://www.xiaodoubi.com/bot/chat.php'
        try:
            r = requests.post(url, data={'chat': word})
            return r.content
        except:
            return "让我一个人静静 T_T..."

    def _simsimi(self, word):
        key = ''
        url = 'http://sandbox.api.simsimi.com/request.p?key=%s&lc=ch&ft=0.0&text=%s' % (
            key, word)
        r = requests.get(url)
        ans = r.json()
        if ans['result'] == '100':
            return ans['response']
        else:
            return '你在说什么，风太大听不清列'

    def _xiaojingling_post(self, word):
        word = word.lstrip()
        print '###' + word + '#### _xiaojingling_post'
        if word == '帮助' or word == 'help':
            return '@我+空格+想说的内容 或者 小精灵+空格+想说的内容就OK啦~'

        url = 'http://www.tuling123.com/openapi/api'
        key = 'ea959464aae817745c0789ecb91776a7'
        try:
            r = requests.post(url, data={'key': key, 'info': word, 'loc': '河北省廊坊市', 'userid': 123456})
            ans = r.json()
            if int(ans['code']) == 100000:  # 文本类
                return ans['text']
            elif int(ans['code']) == 200000:  # 链接类
                return ans['text'] + ' ' + ans['url']
            elif int(ans['code']) == 302000:  # 新闻类
                return '找到对应的新闻了，但是就不告诉你[Smug] '
            elif int(ans['code']) == 308000:  # 菜谱类
                return '找到对应的菜谱了，但是就不告诉你[Smug] 吃货'
            else:
                return '你在说什么，风太大听不清列'
        except:
            return "让我一个人静静 T_T..."

    def _searchContent(self, key, content, fmat='attr'):
        if fmat == 'attr':
            pm = re.search(key + '\s?=\s?"([^"<]+)"', content)
            if pm:
                return pm.group(1)
        elif fmat == 'xml':
            pm = re.search('<{0}>([^<]+)</{0}>'.format(key), content)
            if not pm:
                pm = re.search(
                    '<{0}><\!\[CDATA\[(.*?)\]\]></{0}>'.format(key), content)
            if pm:
                return pm.group(1)
        return '未知'

    def _autoReply(self, ans, toUserName):
        print ("self.autoReplyMode:" + str(self.autoReplyMode))
        fn = 'config/autoReply.txt'
        if toUserName != self.User['UserName']:
            try:
                file_object = open(fn)
                try:
                    self.autoReplyMode = file_object.read()
                    rep = False
                    # -1 关闭自动回复
                    # 0  回复群组和个人
                    # 1  仅回复群组【默认值】
                    # 2  仅回复个人用户
                    if toUserName[:2] != '@@':  # 个人用户
                        rep = (self.autoReplyMode == "0") or (self.autoReplyMode == "2")
                    else:  # 群组
                        rep = (self.autoReplyMode == "0") or (self.autoReplyMode == "1")

                    if rep == True:
                        if self.getUserRemarkName(toUserName)=='桌客桌游狼人杀群和策略游戏群':
                            if self.webwxsendmsg('小萱老师不让说话 [闭嘴][闭嘴][闭嘴]', toUserName):
                                print '自动回复: 小萱老师不让说话 [闭嘴][闭嘴][闭嘴]|' + ans
                                self._info('自动回复: 小萱老师不让说话 [闭嘴][闭嘴][闭嘴]|' + ans)
                            else:
                                print '自动回复失败'
                                self._info('自动回复失败')
                        else: #不回复 桌客桌游狼人杀群和策略游戏群 的消息
                            if self.webwxsendmsg(ans, toUserName):
                                print '自动回复: ' + ans
                                self._info('自动回复: ' + ans)
                            else:
                                print '自动回复失败'
                                self._info('自动回复失败')
                finally:
                    file_object.close()
            except:
                print("config file not fond")

    def _switchautoReplyMode(self, mode):
        fn = 'config/autoReply.txt'

        with open(fn, 'w+') as f:
            f.write(mode)

    def _log(self, str=""):
        if self.DEBUG:
            logging.debug(str)

    def _info(self, str=""):
        if self.DEBUG:
            logging.info(str)


class UnicodeStreamFilter:
    def __init__(self, target):
        self.target = target
        self.encoding = 'utf-8'
        self.errors = 'replace'
        self.encode_to = self.target.encoding

    def write(self, s):
        if type(s) == str:
            s = s.decode('utf-8')
        s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
        self.target.write(s)

    def flush(self):
        self.target.flush()


if sys.stdout.encoding == 'cp936':
    sys.stdout = UnicodeStreamFilter(sys.stdout)

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    import coloredlogs

    coloredlogs.install(level='DEBUG')
    webwx = WebWeixin()
    webwx.loadConfig({'DEBUG': False,
                      'autoReplyMode': "1",
                      'user_agent': None,
                      'interactive': True,
                      'autoOpen': False})
    # autoReplyMode:
    # -1 关闭自动回复
    # 0  回复群组和个人
    # 1  仅回复群组【默认值】
    # 2  仅回复个人用户
    print(webwx)
    fn = 'msgs/msg.json'
    with open(fn, 'a') as f:
        f.write(str(webwx) + '\n\n')
    webwx.start()

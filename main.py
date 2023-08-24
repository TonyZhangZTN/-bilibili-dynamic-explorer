import os
import requests
import json
import shutil
from requests.adapters import HTTPAdapter
import re
import difflib
import pymysql
import time, datetime
import random
APIURL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/space"
debug = False
# buvid3 is a token generated by a js or wasm file under the domain space.bilibili.com
# which is hard to find the algorithm to generate it now, so for simplicity just find it and pass it to our program
buvid3 = ""
def quickGet(url,params):
	headers = {
	"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36",
	}
	cookies = {
		"buvid3":buvid3
	}
	try:
		s = requests.Session()
		s.mount('http://',HTTPAdapter(max_retries=100))#设置重试次数为10次
		s.mount('https://',HTTPAdapter(max_retries=100))
		buffer = s.get(url,params=params,timeout=1, headers = headers,cookies=cookies)
	except requests.exceptions.ConnectionError as e:
		print("连接超时")
	buffer.encoding="utf-8"
	if debug == True:
		print(buffer.text)
	return buffer.text
#获取一列动态中的最大动态id和时间戳，只用于查找动态id范围用
def findMaxIdAndTime(uid,did):
	arg={'host_mid':uid,'offset':did+1,'timezone_offset':-480}
	js = json.loads(quickGet(APIURL,arg))
	if 'items' in js['data'] and len(js['data']['items']) > 0:
		return int(js['data']['items'][0]['id_str']),js['data']['items'][0]['modules']['module_author']['pub_ts']
	else:
		return -1,-1
#获取顶层动态ID
def getTopId(uid):
	arg={'host_mid':uid,'timezone_offset':-480,"features":"itemOpusStyle,listOnlyfans"}
	text = quickGet(APIURL,arg)
	#print(text)
	js = json.loads(text)
	if 'items' in js['data'] and len(js['data']['items']) > 0:
		return int(js['data']['items'][0]['id_str'])
	else:
		return -1

# 打印并保存
def printFromBackToFront(uid,frontId,backId,filename):
	# -480  是GMT+8的意思
	# 之所以+1是因为直接请求这个动态id的返回数据不包含此动态id的内容
	arg = {'host_mid':uid,'offset':backId+1,'timezone_offset':-480}
	cnt = 0
	flag = True
	with open(filename,'w',encoding='utf-8') as fo:
		# write header to the archive html file
		fo.write("<html><head><title>"+filename+"</title><head/><body>")
		while flag == True:
			sleepTime = 0.45 + random.random()/10
			time.sleep(sleepTime)
			data = json.loads(quickGet(APIURL,arg))
			#print(data)
			#print(" sleepTime:" + str(sleepTime))
			if 'items' in data['data']:
				for i in data['data']['items']:
					print(json.dumps(i))
					cnt += 1
					fo.write("<hr><p>"+'倒数第'+str(cnt)+'条动态'+"</p>")
					print('倒数第'+str(cnt)+'条动态')
					fo.write("<p>"+'日期:'+time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(i['modules']['module_author']['pub_ts']))+"</p>")
					print('日期:'+time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(i['modules']['module_author']['pub_ts'])))
					fo.write("<p>"+'<a href=\"https://t.bilibili.com/'+str(i['id_str'])+"\">动态url</a></p>")
					print('动态id:'+str(i['id_str']))

					# set target status id in next request 
					arg['offset'] = i['id_str']
					modules = i["modules"]
					dynamic = modules["module_dynamic"]
					# major might be null in a dynamic
					major = modules["module_dynamic"]["major"]
					# FORWARD
					if i['type'] == "DYNAMIC_TYPE_FORWARD":
						name = modules["module_author"]["name"]
						orig_modules = i["orig"]["modules"]
						orig_author = orig_modules["module_author"]["name"]
						orig_dynamic = orig_modules["module_dynamic"]
						orig_major = orig_dynamic["major"]
						print('用户:'+name)
						if("text" in modules["module_dynamic"]["desc"]):
							forwarded_message = modules["module_dynamic"]["desc"]["text"]
							fo.write("<p>"+'转发内容:\n'+forwarded_message+"</p>)")
							print('转发内容:\n'+forwarded_message)

						# begin a div to contain the forwarded content
						fo.write("<div style=\"background-color:rgb(128,128,128);\">")

						fo.write("<p>"+'原作者:'+orig_author+"</p>")
						if i["orig"]["type"] == "DYNAMIC_TYPE_DRAW":
							#图文
							if(orig_dynamic['desc'] != None):
								if("text" in orig_dynamic['desc']):
									if (orig_dynamic['desc']["text"] != None):
										fo.write("<p>"+orig_dynamic['desc']["text"]+"<br></p>")
										print(orig_dynamic['desc']["text"])
							# traverse each image
							
							if (orig_major["type"] == "MAJOR_TYPE_NONE"):
								fo.write("<p>该图文已被删除</p>")
								print("该图文已被删除")
							elif(orig_major["type"] == "MAJOR_TYPE_DRAW"):
								for j in orig_major['draw']["items"]:
									fo.write("<img src=\""+j['src']+"@100w_100h_1e_1c.webp\" width=\"100px\" height=\"100px\"/>")
								fo.write("<p><br>")
						elif i["orig"]["type"] == "DYNAMIC_TYPE_WORD":
							#正文
							fo.write('正文:\n'+orig_dynamic['desc']['text'])
							print('正文:\n'+orig_dynamic['desc']['text'])
						elif i["orig"]["type"] == "DYNAMIC_TYPE_AV":
							#视频
							if (orig_major["type"] == "MAJOR_TYPE_NONE"):
								fo.write("<p>该视频已被删除</p>")
								print("该视频已被删除")
							elif (orig_major["type"] == "MAJOR_TYPE_ARCHIVE"):
								orig_archive = orig_major["archive"]
								fo.write('视频:\n'+orig_archive['title']+'<br>描述:\n'+orig_archive['desc'])
								print('视频:\n'+orig_archive['title']+'描述:\n'+orig_archive['desc'])
							else:
								fo.write("<p> unknown video source, not in archive mode</p>")
								print("unknown video source, not in archive mode")
						elif i["orig"]["type"] == "DYNAMIC_TYPE_ARTICLE":
							#专栏
							if (orig_major["type"] == "MAJOR_TYPE_ARTICLE"):
								title = orig_major['article']['title']
							elif(orig_major["type"] == "MAJOR_TYPE_OPUS"):
								title = orig_major['opus']['title']
							fo.write("<p>"+'专栏:\n'+title+"</p>")
							print('专栏:\n'+title)
						elif i["orig"]["type"] == "DYNAMIC_TYPE_NONE":
							#专栏
							fo.write("该动态已被删除")
							print("该动态已被删除")
						else: 
							# Unhandled type in forwarded message
							print("Unhandled type in forwarded message:%s"%(i["orig"]["type"]))
							fo.write("<p>"+"Unhandled type in forwarded message:%s"%(i['type'])+"</p>")
						fo.write("</div>")
		
					elif i['type'] == "DYNAMIC_TYPE_DRAW":
						#图文
						fo.write("<p>"+'图文:\n'+dynamic['desc']['text']+"</p><br><div>")
						for j in major['draw']["items"]:
							fo.write("<img src=\""+j['src']+"@100w_100h_1e_1c.webp\" width=\"100px\" height=\"100px\"/>")
						fo.write("</div><br>")
						print('图文:\n'+modules["module_dynamic"]['desc']['text'])
					elif i['type'] == "DYNAMIC_TYPE_WORD":
						#正文
						fo.write("<p>"+'正文:\n'+dynamic['desc']['text']+"</p>")
						print('正文:\n'+dynamic['desc']['text'])
					elif i['type'] == "DYNAMIC_TYPE_AV":
						#视频
						if (major["type"] == "MAJOR_TYPE_NONE"):
							fo.write("<p>该视频已被删除</p>")
							print("该视频已被删除")
						elif (major["type"] == "MAJOR_TYPE_ARCHIVE"):
							archive = major["archive"]
							fo.write("<p>"+'视频:\n'+archive['title']+'<br>描述:\n'+archive['desc']+"</p>")
							print('视频:\n'+archive['title']+'描述:\n'+archive['desc'])
						else:
							fo.write("<p> unknown video source, not in archive mode</p>")
							print("unknown video source, not in archive mode")
					elif i['type'] == "DYNAMIC_TYPE_ARTICLE":
						#专栏
						if (major["type"] == "MAJOR_TYPE_ARTICLE"):
							title = major['article']['title']
						elif(major["type"] == "MAJOR_TYPE_OPUS"):
							title = major['opus']['title']
						fo.write("<p>"+'专栏:\n'+title+"</p>")
						print('专栏:\n'+title)
					else: 
						# Unhandled type
						print("Unhandled type:%s"%(i['type']))
						fo.write("<p>"+"Unhandled type:%s"%(i['type'])+"</p>")
					print("\n\n")
					
					if int(i['id_str'])<=frontId:
						print("Fetching and printing done, exiting the program")
						flag = False
						break
			else:
				print("Error in response: no items")
				break
		fo.write("</body>\n</html>\n")
		fo.close()

def findBottomId(uid,end):
	cnt = 0
	l = 1 #没有动态id是1的动态，当成最小值
	r = end # 传入topId，最大id
	bottomId = -1 #默认id为-1，即异常
	while l<=r:
		sleepTime = 0.45 + random.random()/10
		time.sleep(sleepTime)
		m = (l+r)//2
		cnt = cnt + 1
		mid,mt = findMaxIdAndTime(uid,m)#如果无就是-1
		#*mid<=m，有m不一定存在mid,不能直接从找到的mid缩小范围，否则可能漏*
		print("findBottomId")
		print('depth'+str(cnt) +" sleepTime:" + str(sleepTime))
		print("l=%d\nr=%d\nm=%d"%(l,r,m))
		print("mid="+str(mid)+'\n\n')
		if mid>0 :
			bottomId = mid
			r = m - 1
		else:
			l = m + 1
	return bottomId
#找时间大于等于frontTime的第一个动态id
#--------------------------------------------------------------------
#                 | did   
#Front            |  mt                                          Back
#            front|time
#--------------------------------------------------------------------
def findFrontId(uid,fronttime,l,r):
	cnt = 0
	frontId = l
	while l<=r:
		sleepTime = 0.45 + random.random()/10
		time.sleep(sleepTime)
		m = (l+r)//2
		cnt = cnt + 1
		mid,mt = findMaxIdAndTime(uid,m)
		print("findFrontId")
		print('depth'+str(cnt)+" sleepTime:" + str(sleepTime))
		print("l=%d\nr=%d\nm=%d"%(l,r,m))
		print("mid="+str(mid))
		if mt > 0:
			print("time:"+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))+'\n\n')
			if mt>=fronttime :
				frontId = mid
				r = m - 1
			else:
				l = m + 1
		else:
			r = m - 1
	return frontId
#找时间小于等于backTime的第一个动态id
def findBackId(uid,backtime,l,r):
	cnt = 0
	backId = r
	while l<=r:
		sleepTime = 0.45 + random.random()/10
		time.sleep(sleepTime)
		m = (l+r)//2
		cnt = cnt + 1
		mid,mt = findMaxIdAndTime(uid,m)
		print("findBackId")
		print('depth'+str(cnt)+" sleepTime:" + str(sleepTime))
		print("l=%d\nr=%d\nm=%d"%(l,r,m))
		print("mid="+str(mid))
		if mt > 0:
			print("time:"+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mt))+'\n\n')
			if mt<=backtime :
				backId = mid
				l = m + 1
			else:
				r = m - 1
		else:
			l = m + 1
	return backId
def main():
	#uid = input("uid:")
	uid = "12246"
	global buvid3
	# buvid3 = input("Please input buvid3 token:").strip()
	buvid3 = "D16402AB-DA6F-15D3-01FC-C84871726F9211419infoc"
	text = quickGet("https://api.bilibili.com/x/space/wbi/acc/info",{'platform':'web','mid':uid,'jsonp':'jsonp'})
	print(text)
	data = json.loads(text)
	filename = data['data']['name']+".html"
	print("user:"+data['data']['name'])
	operation = input("mode\n1:all\t2:range")
	if(operation == "2"):
		timestr = input("begin: YYYY-MM-DD HH:MM:SS\n")
		fronttime = int(time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S")))

		timestr = input("till when?: YYYY-MM-DD HH:MM:SS\n")
		backtime = int(time.mktime(time.strptime(timestr, "%Y-%m-%d %H:%M:%S")))
	topId = getTopId(uid)
	bottomId = 1
	if topId == -1:#l
		print("此人无动态")
		exit()
	else:
		#bottomId = findBottomId(uid,topId)
		pass
		#print('第一个动态id:'+str(bottomId))
	if(operation == "1"):
		frontId = 4915139101108543
		backId = 163515860295773425
	elif(operation == "2"):
		frontId = findFrontId(uid,fronttime,bottomId,topId)
		backId = findBackId(uid,backtime,bottomId,topId)
		#print("范围内最早id%d，最晚id%d"%(frontId,backId))
	printFromBackToFront(uid,frontId,backId,filename)
if __name__ == '__main__':
	main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Date    : 2018-04-02 18:03:21
# @Author  : ${guoshengkang} (${kangguosheng1@huokeyi.com})

import os
import json
import demjson
import pandas as pd
import datetime
# 导入自定义的包
from integrated_regression_model import *
from integrated_timeseries_model import *
from integrated_deeplearning_model import *

def nonintelligent_model(input_data_df=None,config_data_df=None,date_start=None,date_end=None,time2market=None,forcast_model='GBRT',
	evaluation='MAPE',length_merge=1,period=7,required_data_number=5):
	'''
	非智能的预测方法
	--input parameters--
	df:预测的输入数据--df.columns=['id','date','quantity','tag_price','fact_price'] #必须列
	date_start:历史数据的开始日期--str
	date_end:历史数据的结束日期--str
	time2market:产品的上市日期--str
	test_size:测试数据的比例
	forcast_model:预测模型
	evaluation:预测评估方法
	length_merge:数据合并的天数
	period:预测的周期
	required_data_number:需要要的训练样本数据量
	'''
	# 移除重复数据
	df=input_data_df.drop_duplicates()
	df_config=config_data_df.drop_duplicates()
	# 预测天数
	predict_days=length_merge*period
	# 结果列表
	list_result=[]
	# 所有的对象id
	obj_ids=df['id'].unique() 
	# 循坏每个id
	for id in obj_ids: 
		dict_result=dict()
		dict_result['id']=str(id) # TypeError: Object of type 'int64' is not JSON serializable
		dict_result['model']=forcast_model
		df_tmp=df[df['id']==id] # 将id对应的所有数据取出来
		# 删除类别列
		if 'class' in df.columns:
			df.drop(['class'],axis=1,inplace=True)

		# (1) 数据检查
		# 先检查有没有,再检查够不够
		df_train=df_tmp[df_tmp['label']==0] #训练数据
		if df_train.empty:
			dict_result['code']=1000
			dict_result['desc']='训练数据为空'
			list_result.append(dict_result)
			continue
		df_predict=df_tmp[df_tmp['label']==1] #预测数据
		if df_predict.empty:
			dict_result['code']=1001
			dict_result['desc']='预测数据为空'
			list_result.append(dict_result)
			continue
		try:
			# 获取上市日期
			date_market=time2market[str(id)] 
		except:
			dict_result['code']=1002
			dict_result['desc']='缺少产品上市时间'
			list_result.append(dict_result)
			continue
		if len(df_predict)!=predict_days:
			dict_result['code']=1003
			dict_result['desc']='预测数据不足'
			list_result.append(dict_result)
			continue
		sale_days=len(df_train) # 有销量的天数
		dict_result['sale_days']=sale_days
		if sale_days<required_data_number:
			dict_result['code']=1004
			dict_result['desc']="有销量的数据不足%d天(为%d天)"%(required_data_number,sale_days)
			if forcast_model=='SMA' or forcast_model=='WMA':
				pass
			else:
				list_result.append(dict_result)
				continue
		# 删除标签列
		if 'label' in df_tmp.columns:
			df_tmp.drop(['label'],axis=1,inplace=True)

		# (2) 数据填充
		date_market=datetime.datetime.strptime(date_market,'%Y-%m-%d')
		date_min=max(date_start, date_market) # 最小日期数据
		date_max=max(df_tmp['date'])  # 按预测数据来取最大日期
		# 填充缺失日期的数据--训练+测试数据
		df_tmp_config=df_config[(df_config['date']>=date_min) & (df_config['date']<=date_max)]  # 取出holiday和season数据
		df_tmp=pd.merge(df_tmp_config,df_tmp,left_on='date',right_on='date',how='left') # 左连接,所有日期
		df_tmp.fillna({'quantity':0,'promotion':0},inplace=True)     # 将所有缺失的quantity/promotion数据填充为0
		df_tmp=df_tmp.sort_values(by='date')     # 数据填充之前先将数据按时间排序
		df_tmp.fillna(method='ffill',inplace=True)     # 用前置项方式填充其他缺失数据
		# 对上市时间但没有销量时时有用
		df_tmp.fillna(method='bfill',inplace=True)     # 用后置项方式填充其他缺失数据
		
		# (3) 模型训练及滚动预测 integrated_deeplearning_model
		try:
			if forcast_model in regression_methods:
				y_real,y_fit,y_predict,error_fit=integrated_regression_model(df=df_tmp,forcast_model=forcast_model,evaluation=evaluation,length_merge=length_merge,period=period)
			elif forcast_model in timeseries_methods:
				y_real,y_fit,y_predict,error_fit=integrated_timeseries_model(df=df_tmp,forcast_model=forcast_model,evaluation=evaluation,length_merge=length_merge,period=period)
			elif forcast_model in deeplearning_methods:
				y_real,y_fit,y_predict,error_fit=integrated_deeplearning_model(df=df_tmp,forcast_model=forcast_model,evaluation=evaluation,length_merge=length_merge,period=period)
			else:
				dict_result['code']=1005
				dict_result['desc']="找不到该模型:%s"%forcast_model
				list_result.append(dict_result)
				continue
		except Exception as e:
			dict_result['error']='模型调用失败(%s)'%(e)
			list_result.append(dict_result)
			continue
		dict_result['y_real']=y_real
		dict_result['y_fit']=y_fit
		dict_result['y_predict']=y_predict
		dict_result[evaluation]=error_fit
		# 将id的预测结果dict_result添加到结果列表
		list_result.append(dict_result)
	# 结束循环每个id的预测
	json_result = json.dumps(list_result)
	return json_result

########################################################################################
# 测试代码
if __name__=='__main__':
	# 导入数据
	fin_path = os.path.join(os.path.split(os.path.realpath(__file__))[0], "input_data.csv")
	dateparse = lambda x: pd.datetime.strptime(x, '%Y-%m-%d')
	input_data_df=pd.read_csv(fin_path, parse_dates=['date'], date_parser=dateparse)

	config_path = os.path.join(os.path.split(os.path.realpath(__file__))[0], "config_date_holiday_season_weekend.csv")
	dateparse = lambda x: pd.datetime.strptime(x, '%Y-%m-%d')
	config_data_df=pd.read_csv(config_path, parse_dates=['date'], date_parser=dateparse)
	config_data_df.drop(['hld_label'],axis=1,inplace=True) # 删除hld_label列,直接修改

	# 定义上市日期
	time2market="[{'43791':'2018-01-28','41841':'2018-01-28','11111':'2018-01-28'}]"
	time2market = demjson.decode(time2market)[0]
	# 定义开始结束日期
	date_start='2018-01-28'
	date_end='2018-04-25'
	date_start=datetime.datetime.strptime(date_start,'%Y-%m-%d')
	date_end=datetime.datetime.strptime(date_end,'%Y-%m-%d')
	json_result=nonintelligent_model(input_data_df,config_data_df,date_start=date_start,date_end=date_end,time2market=time2market,
			forcast_model='LSTM',evaluation='MAPE',length_merge=1,period=7)
	text = json.loads(json_result)
	# 打印预测结果
	for x in text:
		print(x)

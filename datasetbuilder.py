import os
import sys
import pandas as pd
import enum
import dataset
from dataset import *
from datetime import timedelta
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from statistics import mean
from sklearn.preprocessing import MinMaxScaler
from sklearn.decomposition import PCA
sys.path.insert(0, './data')
import sitedict
from sitedict import *

# used in format_date() and get_past_dates()
from datetime import datetime
from dateutil.relativedelta import relativedelta

import numpy as np # used in _encode_cyclical_data()

class Timestep(enum.Enum):
    daily = 1
    weekly = 2

# Builder for DataSet class
class DataSet_Builder():



    def __init__(self):
        # defaults
        self.xcols = []
        self.ycols = []
        self.timestep = Timestep.daily

        # data is in a folder called data
        csvpath = os.path.join(os.getcwd(), "data", "merged.csv")
        pklpath = os.path.join(os.getcwd(), "data", "data.pkl")

        if os.path.exists(pklpath):
            self.df = pd.read_pickle(pklpath)
        else:
            self.df = pd.read_csv(csvpath, sep=",")
            self.df.to_pickle(pklpath)

        self.format_date()


    # encodes dates so that cyclical nature of days in year is preserved
    def format_date(self):
        
        if self.timestep == Timestep.daily:
            print("daily")

            self.df['date_object'] = [datetime.strptime(date, '%m/%d/%Y') for date in self.df['Date']]
            
            self.df['day_of_year'] = [date_object.timetuple().tm_yday for date_object in self.df['date_object']]

            # data['day'] = data.datetime.dt.month
            self._encode_cyclical_data('day_of_year', 365) # does not account for leap years; negligible difference
            
            # FIXME insert date_object col to front of xcols

            # TODO be able to take a future date (ex. 2020-07-18) and return 2019-07-18, 2018-07-18, etc. (+/- 1 day)
                # ACCOUNT FOR leap years, removed outliers (search for closest day, or leave out of average?)
            

            print(self.df)


        # convert daily to weekly
        if self.timestep == Timestep.weekly:
            print('weekly')


            def _weekly_average(self):
                print(self.df)
                self.df['Date'] = pd.to_datetime(self.df['Date']) - pd.to_timedelta(7, unit='d')
                self.df = self.df.groupby(['Site Id', pd.Grouper(key='Date', freq='W-MON')]).mean().reset_index()
                print(self.df)
                return self.df
    
    def _encode_cyclical_data(self, col_name, max_val):
        self.df[col_name + '_sin'] = np.sin(2 * np.pi * self.df[col_name]/max_val)
        self.df[col_name + '_cos'] = np.cos(2 * np.pi * self.df[col_name]/max_val)

    # given a date ('year-month-day' string) in the future, returns a list that contains data from past dates at the same time in the year
    # if timestep is weekly, round supplied date to the date at beginning of week
    def get_past_dates(self, future_date, time_step):
        date_format_string = '%Y-%m-%d'
        
        # find the first year in the dataset
        first_date = self.df['Date', 0]
        first_date_object = datetime.strptime(first_date, date_format_string)
        first_year = first_date_object.year

        if time_step == 'daily':
            future_date_object = datetime.strptime(future_date, date_format_string)
        else: # if time_step == 'weekly'
            date_obj = datetime.strptime(future_date, date_format_string).date()
            future_date_object = date_obj - timedelta(days=date_obj.weekday())
        
        # start at the first year with the matching day
        past_date = datetime.datetime(first_year, future_date_object.month, future_date_object.day)

        list_of_dates = []
        while past_date < future_date_object:
            yesterday = past_date - timedelta(days=1)
            tomorrow = past_date - timedelta(days=1)
            list_of_dates.append(yesterday.strftime(date_format_string))
            list_of_dates.append(past_date.strftime(date_format_string))
            list_of_dates.append(tomorrow.strftime(date_format_string))
        
        past_dates = self.df[self.df['Date'].isin(list_of_dates)] # note: might be inefficient

        # while past_date < future_date_object:
        #     past_dates.append(self.df.loc[df['Date'] == past_date.strftime(date_format_string)]) # FIXME how efficient is this retrieval??
        #     past_date = past_date + relativedelta(years = 1) # go to same date, 1 year in the future

        # if self.df['Date'] == past_date.strftime(date_format_string):
        #     past_dates.append(row)

        return past_dates



    def remove_outliers(self):
        #optional
        # TODO
        # Prints number of outliers found with IsolationForest
        # Returns a new df that doesn't contain the outliers
        clf = IsolationForest(n_estimators=20, contamination=0.1, behaviour='new')
        pred = clf.fit_predict(self.df.loc[:,self.xcols + self.ycols])
        self.df = self.df[pred!=-1]
        self.df = self.df.reset_index(drop=True)

    def set_xcols(self, xcols):
        self.xcols = xcols

    def set_ycols(self, ycols):
        self.ycols = ycols

    def set_timestep(self, timestep):
        # timestep is a string
        # acceptable strs: daily, weekly
        self.timestep = Timestep[timestep]

    def use_pca(self):
        # change df, xcols, and ycols appropriately
        pca = PCA(.95)
        old_df = self.df[self.xcols]
        principalComponents = pca.fit_transform(old_df) # #drop(['Date'], axis=1)
        principalDf = pd.DataFrame(data = principalComponents)
        self.df = self.df.drop(self.xcols, axis=1)
        self.df = pd.concat([self.df, principalDf], axis=1)

        self.xcols = list(principalDf.columns)

    def scale_data(self):
        # min max scaling just on the xcols
        # optional
        scaler = MinMaxScaler()
        scaler.fit(self.df.loc[:,self.xcols])
        self.df[self.xcols] = scaler.transform(self.df.loc[:,self.xcols])

    def use_rect_radius(self, proportion):
        # proportion is a number 0-1 where 1 is all sites, 0 is none
        # 0.5 contains approximately half the sites centered at the CoM
        self.df = self._get_df_of_radius(proportion)

    def build_dataset(self):

        self._use_timestep()
        return DataSet(self.df, self.xcols, self.ycols)

    def clean_df(self):
        # drop off rows with blank values for x or y col
        # treat -99.9 as NaN
        for col in self.xcols + self.ycols:
            self.df.drop(self.df.index[self.df[col] == -99.9], inplace = True)
        self.df = self.df.dropna(subset=self.xcols+self.ycols)
        self.df = self.df.reset_index(drop=True)

    def _use_timestep(self):
        # if timestep is weekly, average for the week

        if self.timestep == Timestep.weekly:
            self._weekly_average()

    def _weekly_average(self):
<<<<<<< HEAD
        # print(self.df)
=======
        # round down the week
<<<<<<< HEAD


=======
>>>>>>> 5f5b7ba85d50af454e31ae08b18fa3e76717cc93
>>>>>>> 52c871f56fe6e4accdee96c6f2483d0733abbbec
        self.df['Date'] = pd.to_datetime(self.df['Date']) - pd.to_timedelta(7, unit='d')

        # within a site, average same dates
        self.df = self.df.groupby(['Site Id', pd.Grouper(key='Date', freq='W-MON')]).mean().reset_index()
<<<<<<< HEAD
        # print(self.df)
        return self.df
=======
>>>>>>> 5f5b7ba85d50af454e31ae08b18fa3e76717cc93

    # Returns a df of sites within a specified radius proportion
    def _get_df_of_radius(self, proportion, df=None):
        # Notes on proportion: this is not the proportion of sites to keep
        # Proportion is (proportion of area to keep around center)^2
        #   That means a proportion of 0.5 keeps a quarter of the total area

        # The main problem with this method is you lose the min & max for both
        # latitude and longitude until the proportion is exactly 1

        # proportion        % remaining
        # 0.1               8.8
        # 0.25              13.1
        # 0.5               44.8
        # 0.75              71.4
        # 0.9               78.6
        # 0.95 - 0.9999     89.2

        # center of mass of points
        long_center, lat_center = self._get_center_coordinates()

        # min and max of latitude and longitude
        long_min, long_max = self._get_min_max("long")
        lat_min, lat_max = self._get_min_max("lat")

        # acceptable range is a box that grows with proportion away from the
        # center of mass
        long_range = [long_center - (long_center - long_min) * proportion,
                        long_center + (long_max - long_center) * proportion]
        lat_range = [lat_center - (lat_center - lat_min) * proportion,
                        lat_center + (lat_max - lat_center) * proportion]

        # sites within the acceptable range
        valid_sites = []
        for site in SITEDICT.keys():
            if (float(SITEDICT[site]["lat"]) >= lat_range[0] and
                float(SITEDICT[site]["lat"]) <= lat_range[1] and
                float(SITEDICT[site]["long"]) >= long_range[0] and
                float(SITEDICT[site]["long"]) <= long_range[1]):
                valid_sites.append(site)

        if df is None:
            df = self.df

        return df[df["Site Id"].isin(valid_sites)].reset_index(drop=True)


    def _get_center_coordinates(self):
        sites = list(SITEDICT.keys())
        longitude_center = mean(float(SITEDICT[site]["long"]) for site in sites)
        latitude_center = mean(float(SITEDICT[site]["lat"]) for site in sites)
        return longitude_center, latitude_center

    def _get_min_max(self, key_str):
        minv = min(float(SITEDICT[site][key_str]) for site in SITEDICT.keys())
        maxv = max(float(SITEDICT[site][key_str]) for site in SITEDICT.keys())
        return minv, maxv


    # probably deleting

    # # Returns a cleaned dataframe with the columns of the features removed
    # # features: an array of strings of feature names
    # # ex. ['mpg', 'car name']
    # # df (optional): dataframe, if not specified will use self.df
    # def remove_features(self, features, df=None):
    #     if df is None:
    #         df = self.df
    #     self.cleaned_df = df.drop(features, axis=1)
    #     return self.cleaned_df

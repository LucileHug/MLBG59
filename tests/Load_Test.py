from MLKit.Load.Load import *
import unittest
import pandas as pd

file='MLKit/tests/df_test.csv'

class Test_Load(unittest.TestCase):
    
    #
    def test_get_delimiter(self):
        self.assertEqual(get_delimiter(file),',')
        
    def test_load(self):
        self.assertIsNotNone(type(load_data(file=file, verbose=0)),pd.DataFrame)
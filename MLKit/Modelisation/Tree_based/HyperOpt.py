import xgboost
import random
import itertools as it
# import datetime
from MLKit.Modelisation.Techniques.Bagging import *
from MLKit.Utils.Utils import *
from MLKit.Utils.Display import color_print
from datetime import datetime

"""
Defaults HP grid for RF and XGBOOST
"""
default_RF_grid_param = {
    'n_estimators': np.random.uniform(low=20, high=200, size=20).astype(int),
    'max_features': ['auto', 'log2'],
    'max_depth': np.random.uniform(low=3, high=10, size=20).astype(int),
    'min_samples_split': [5, 10],
    # 'min_samples_leaf': [1, 2, 4]
}

default_XGB_grid_param = {
    'n_estimators': np.random.uniform(low=100, high=400, size=20).astype(int),
    'max_features': ['auto', 'log2'],
    'max_depth': np.random.uniform(low=3, high=10, size=20).astype(int),
    'min_samples_split': [5, 10, 15],
    'min_samples_leaf': [1, 2, 4, 8],
    'learning_rate': [0.001, 0.003, 0.006, 0.009, 0.01, 0.03, 0.06, 0.09, 0.1, 0.3, 0.6],
    'scale_pos_weight': [3, 4, 5, 6, 7, 8, 9],
}

"""
-------------------------------------------------------------------------------------------------------------
"""


class Hyperopt(object):
    """ 
    For a selected algorithm and a hyper-parameters grid.
    Pick N random HPs combinations and train/predict the models
    
    Parameters
    ---------
     > classifier : string (Default : 'RF')
          classifier
     > grid_param : dict (Default : default_RF_grid_param)
          HPs grid
     > n_param_comb : int (Default : 10)
          number of HPS combinations
       
    Attributes
    ---------
     > dict_roc_train : dict
     > dict_models : dict
     > dict_features_imp : dict
     > dict_bagging : dict
     > df_models_summ : DataFrame
    """

    def __init__(self,
                 classifier='RF',
                 grid_param=None,
                 n_param_comb=10,
                 top_bagging=False,
                 bagging_param=default_bagging_param,
                 comb_seed=None):

        # parameters
        if grid_param is None:
            grid_param = default_RF_grid_param
        self.classifier = classifier
        self.grid_param = grid_param
        self.n_param_comb = n_param_comb
        self.top_bagging = top_bagging
        self.bagging_param = bagging_param
        self.comb_seed = comb_seed
        # attributes
        self.train_model_dict = None
        self.bagging_object = None

    """
    -------------------------------------------------------------------------------------------------------------
    """

    def get_params(self):
        """"
        return object parameters

        return
        -----
        dict containing parameters
        
        """
        return {'classifier': self.classifier,
                'grid_param': self.grid_param,
                'n_param_comb': self.n_param_comb,
                'top_bagging': self.top_bagging,
                'bagging_param': self.bagging_param,
                'comb_seed': self.comb_seed}

    """
    -------------------------------------------------------------------------------------------------------------
    """

    def train(self, df_train, target, verbose=1):
        """
        Train the models
        
        input
        -----
         > df_train : DataFrame
             training set
         > target : string
             target name
         > verbose : int (0/1) (Default : 1)
             get more operations information
            
        return
        ------
        ...
        """
        # Sort HPs grid dict by param name (a->z)
        grid_names = sorted(self.grid_param)
        # random sampling : 'n_param_comb' HPS combinations
        # list(it.product(*(self.grid_param[Name] for Name in grid_names))) create all the possible combinations
        if self.comb_seed is not None:
            random.seed(self.comb_seed)

        sample_combinations = random.sample(list(it.product(*(self.grid_param[Name] for Name in grid_names))),
                                            k=self.n_param_comb)

        if verbose == 1:
            print('\033[34m' + 'Random among grid search:', self.n_param_comb, 'HP combs',
                  '\033[0m')
            print('\033[34m' + 'Model : ', self.classifier, '\033[0m')

        # init train_model_dict
        self.train_model_dict = {}
        self.bagging_object = {}

        # for each HP combination :
        for l in range(len(sample_combinations)):

            t_ini_model = datetime.now()

            # Model params
            HP_dict = dict(zip(grid_names, sample_combinations[l]))

            # Model creation
            if self.classifier == 'RF':  # Classifier Random Forest
                clf = RandomForestClassifier(**HP_dict)
            elif self.classifier == 'XGBOOST':
                clf = xgboost.XGBClassifier(**HP_dict)

            # X / ycx
            y_train = df_train[target]
            X_train = df_train.drop(target, axis=1)

            # Without bagging
            if not self.top_bagging:

                # model training
                clf_fit = clf.fit(X_train, y_train)
                # features importance
                features_dict = dict(zip(X_train.columns, clf.feature_importances_))
                # classification probas
                y_proba = clf_fit.predict_proba(X_train)[:, 1]
                y_pred = clf_fit.predict(X_train)

            # With bagging
            elif self.top_bagging:

                # init bagging object with default params
                bag = Bagging(clf, **self.bagging_param)
                # model training
                bag.train(df_train, target)
                clf_fit = bag.list_model
                # features importance
                features_dict = bag.feat_importance_BAG_RF(X_train)
                # classification probas
                y_proba, y_pred = bag.predict(df_train.drop(target, axis=1))

                self.bagging_object[l] = bag

            # Model evaluation
            eval_dict = classifier_evaluate(y_train, y_pred, y_proba, print_level=0)

            # store
            train_model = {'HP': HP_dict,
                           'probas': y_proba,
                           'model': clf_fit,
                           'features_importance': features_dict,
                           'evaluation': eval_dict}

            self.train_model_dict[l] = train_model

            t_fin_model = datetime.now()

            if verbose == 1:
                print(str(l + 1) + '/' + str(len(sample_combinations)) +
                      ' >> {} Sec.'.format((t_fin_model - t_ini_model).total_seconds()))

        return self

    """
    -------------------------------------------------------------------------------------------------------------
    """

    def predict(self, df, target, delta_auc, verbose=1):
        """
        Apply the models
        
        input
        -----
         > df : DataFrame
             set to apply the models
         > target : string
             target name
         > verbose : int (0/1) (Default : 1)
             get more operations information
        
        return
        ------
        ...
        
        """
        res_model_dict = {}

        # X / y
        y = df[target]
        X = df.drop(target, axis=1)

        # For each HPs combination
        for key, value in self.train_model_dict.items():

            model = value['model']

            t_ini_model = datetime.now()

            # Without bagging
            if self.top_bagging == False:

                # classification probas
                y_proba = model.predict_proba(X)[:, 1]

                # classification votes
                y_pred = model.predict(X)

            # With bagging
            elif self.top_bagging == True:

                # classification probs and votes
                y_proba, y_pred = self.dict_bagging[key].predict(X)

                # store
            dict_model = {'y_proba': y_proba,
                          'y_pred': y_pred}

            # compute model metrics
            eval_dict = classifier_evaluate(y, y_pred, y_proba, print_level=0)
            fpr_train, tpr_train = self.train_model_dict[key]['evaluation']['fpr tpr']
            eval_dict['delta_auc'] = abs(auc(fpr_train, tpr_train) - eval_dict["Roc_auc"])

            # store 
            res_model_dict[key] = {'predictions': dict_model,
                                   'evaluation': eval_dict}

            # print metrics
            if verbose == 1:
                print(value['HP'])
                if eval_dict['delta_auc'] <= delta_auc:
                    c_code = 32
                else:
                    c_code = 31

                roc_auc_train = auc(fpr_train, tpr_train)
                color_print(
                    ' > AUC train: ' + str(round(eval_dict["Roc_auc"], 3)) + ' test: ' + str(round(roc_auc_train, 3)) +
                    ' / F1: ' + str(round(eval_dict['F1'], 3)) +
                    ' / prec: ' + str(round(eval_dict['Precision'], 3)) +
                    ' / recall: ' + str(round(eval_dict['Recall'], 3)), color_code=c_code)

            t_fin_model = datetime.now()
            if verbose > 0:
                print('{} Sec.'.format((t_fin_model - t_ini_model).total_seconds()))

        return res_model_dict

    """
    -------------------------------------------------------------------------------------------------------------
    """

    def get_best_model(self, test_model_dict, metric='F1', delta_auc_th=0.03, verbose=1):
        """
        get the best model according to a selected metric among valid model (|auc(train)-auc(test)|)

        input
        -----
         > test_model_dict : dict
              key : model index , value : model outputs and metrics
         > metric : string (default = F1-score
              metric used to get the best model
         > delta_auc_th : float
              ...

         return
         ------
          > best model index
          > list containing valid model indexes

        """
        # select valid models (abs(auc_train - auc_test)<0.03)
        valid_model = {}
        for key, param in test_model_dict.items():
            if param['evaluation']['delta_auc'] <= delta_auc_th:
                valid_model[key] = param

        # Best model according to selected metric
        if len(valid_model.keys()) > 0:
            best_model_idx = max(valid_model, key=lambda x: valid_model[x].get('evaluation').get(metric))
            if verbose==1:
                print(' >',len(valid_model.keys()),' valid models |auc(train)-auc(test)|<='+str(delta_auc_th))
                print(' > best model : '+str(best_model_idx))
        else:
            best_model_idx = None
            print('0 valid model')

        return best_model_idx, list(valid_model.keys())

    """
    ---------------------------------------------------------------------------------------------------------------
    """

    def model_res_to_df(self, test_model_dict, sort_metric='F1'):
        """
        store models summary in DataFrame

        input
        -----
         > test_model_dict : dict
              dict containing models informations
         > sort_metric : string (default = 'F1')
              metric to sort models in DataFrame
        return
        ------
        > DataFrame
        """
        # dataFrame columns names
        model_col = ['model_index']
        HP_col = list(self.train_model_dict[0]['HP'].keys())
        bagging_col = ['bagging']
        metrics_col = ['Accuracy', 'Roc_auc', 'F1', 'Logloss', 'Precision', 'Recall', 'delta_auc']
        feat_imp_col = ['TOP_feat1', 'TOP_feat2', 'TOP_feat3', 'TOP_feat4', 'TOP_feat5']

        df_local = pd.DataFrame(columns=model_col + HP_col + bagging_col + metrics_col + feat_imp_col)

        # store informations in df
        for key, value in self.train_model_dict.items():
            dict_tmp = {'model_index': key}
            dict_tmp.update(value['HP'].copy())
            dict_tmp.update({x: test_model_dict[key]['evaluation'][x] for x in metrics_col})
            dict_tmp.update({'bagging': self.top_bagging})
            df_tmp = pd.DataFrame.from_dict(self.train_model_dict[0]['features_importance'],
                                            orient='index').reset_index().rename(
                columns={'index': 'feat', 0: 'importance'}).sort_values(by='importance', ascending=False).head(5)
            serie_tmp = df_tmp['feat'] + ' ' + round(df_tmp['importance'], 5).astype(str)
            dict_tmp.update(dict(zip(feat_imp_col, serie_tmp.tolist())))

            df_local = df_local.append(dict_tmp, ignore_index=True)

        return df_local.loc[df_local['delta_auc'] <= 0.03].sort_values(by=sort_metric, ascending=False)
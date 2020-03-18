from MLBG59.Utils.Display import print_title1
from MLBG59.Utils.Decorators import timer
from MLBG59.Explore.Explore import explore
from MLBG59.Preprocessing.Date import DateEncoder
from MLBG59.Preprocessing.Missing_Values import NAEncoder
from MLBG59.Preprocessing.Outliers import OutliersEncoder
from MLBG59.Preprocessing.Categorical import CategoricalEncoder
from MLBG59.Modelisation.HyperOpt import *
from MLBG59.Select_Features.Select_Features import select_features


class AutoML(pd.DataFrame):
    """Covers the complete pipeline of a classification project from a raw dataset to a deployable model.

    AutoML is built as a class inherited from pandas DataFrame. Each step corresponds to a class method that
    can be called with default or filled parameters.

    - Data exploration (dataset information and outliers analysis)
    - Preprocessing (clean and prepare data)
    - Modelisation (random search)

    Available classifiers : Random Forest and XGBOOST.

    Note : A method can be applied if the previous one has been applied too.
    
    Parameters 
    ----------
    _obj : DataFrame
        Source Dataset
    target : string
        target name
    step : string
        last method applied on object
    d_features : dict (created by audit method)

        {x : list of variables names}

        - date : date features
        - identifier : identifier features
        - verbatim : verbatim features
        - boolean : boolean features
        - categorical : categorical features
        - numerical : numerical features
        - categorical : categorical features
        - date : date features
        - NA : features which contains NA values
        - low_variance : list of the features with low variance

    d_num_outliers : dict (created with get_outliers method)
        {feature : [lower_limit,upper_limit]}
    d_cat_outliers : dict (created with get_outliers method)
        {feature : outliers categories list}
    """

    def __init__(self, *args, target=None):
        super(AutoML, self).__init__(*args)
        # parameters
        self.target = target
        # attributes
        self.step = None
        self.d_features = None

    def __repr__(self):
        return 'MLBG59 instance'

    """
    --------------------------------------------------------------------------------------------------------------------
    """

    @timer
    def explore(self, verbose=False):
        """get and store global information about the dataset :

        - Variables type
        - NA values
        - low variance variables

        
        Parameters
        ----------
        target : string (Default : None)
              target name
        verbose : boolean (Default False)
            Get logging information
            
        Returns
        -------
        dict : self.d_features {x : list of variables names}

        - date : date features
        - identifier : identifier features
        - verbatim : verbatim features
        - boolean : boolean features
        - categorical : categorical features
        - numerical : numerical features
        - categorical : categorical features
        - date : date features
        - NA : features which contains NA values
        - low_variance : list of the features with low variance

        """
        if verbose:
            print('\n')
            print_title1('Explore')

        # call std_audit_dataset function
        self.d_features = explore(
            self, verbose=verbose)

        self.step = 'recap'

        # created attributes display
        if verbose:
            color_print("\nCreated attributes :  d_features (dict) ")
            print("Keys :")
            print("  -> date")
            print("  -> identifier")
            print("  -> verbatim")
            print("  -> boolean")
            print("  -> categorical")
            print("  -> numerical")
            print("  -> date")
            print("  -> NA")
            print("  -> low_variance")

    """
    --------------------------------------------------------------------------------------------------------------------
    """

    @timer
    def get_outliers(self, num_xstd=4, cat_freq=0.05, verbose=False):
        """Identify cat and num features that contain outlier

        * num : x outlier <=> abs(x - mean) > num_xstd * var
        * cat : Modalities with frequency <x% (Default 5%)
        
        Parameters
        ----------
        num_xstd : int (Default : 3)
            Variance gap coefficient
        cat_freq : float (Default : 0.05)
            Minimum modality frequency
        verbose : boolean (Default False)
            Get logging information

        Returns
        -------
        self.d_cat_outliers
            {variable : list of categories considered as outliers}
        self.d_num_outliers
            {variable : [lower_limit, upper_limit]}
        """
        assert self.step == 'recap', 'apply recap method'

        if verbose:
            print_title1('\nGet_outliers')

        # created attributes display
        if verbose:
            color_print("\nCreated attributes : ")
            print("  -> d_num_outliers")
            print("  -> d_cat_outliers")

    """
    --------------------------------------------------------------------------------------------------------------------
    """

    @timer
    def preprocess(self, date_ref=None, process_outliers=False, cat_method='deep_encoder', verbose=False):
        """Prepare the data before feeding it to the model :

            - remove low variance features
            - remove identifiers and verbatims features
            - transform date features to timedelta
            - fill missing values
            - process categorical and boolean data (one-hot-encoding or Pytorch NN encoder)
            - replace outliers (optional)

        you can enable outliers processing if you applied get_outliers() method
        
        Parameters
        ----------
        date_ref : string '%d/%m/%y' (Default : None)
            ref date to compute timedelta.
            If None, today date
        process_outliers : boolean (Default : False)
            Enable outliers replacement (if get_outliers method applied)
        cat_method : string (Default : 'one_hot')
            Categorical features encoding method

            - one_hot
            - deep_encoder

        verbose : boolean (Default False)
            Get logging information
        """
        if process_outliers:
            assert self.step == 'get_outliers', 'apply get_outliers method'
        else:
            assert self.step in ['recap', 'get_outliers'], 'apply recap (and get_outliers) method'

        if verbose:
            print_title1('\nPreprocess')

        target = self.target

        ######################################
        # Remove features with null variance
        ######################################
        if verbose:
            color_print("Remove features with null variance")
            print('  features : ', list(self.d_features['low_variance']))

        df_local = self.copy()

        if self.d_features['low_variance'] is not None:
            for col in self.d_features['low_variance']:
                if col in df_local.columns.tolist() and col != self.target:
                    df_local = df_local.drop(col, axis=1)

        # delete removed cols from num_column
        self.d_features['numerical'] = [x for x in self.d_features['numerical'] if
                                        x not in self.d_features['low_variance']]

        ##########################################
        # Remove identifiers and verbatim features
        ##########################################
        if verbose:
            color_print("Remove identifiers and verbatims features")
            print('  identifiers  : ', list(self.d_features['identifier']))
            print('  verbatims  : ', list(self.d_features['verbatim']))

        for typ in ['identifier', 'verbatim']:
            if self.d_features[typ] is not None:
                for col in self.d_features[typ]:
                    if col in df_local.columns.tolist() and col != self.target:
                        df_local = df_local.drop(col, axis=1)

        ####################################################
        # Transform date -> time between date and date_ref
        ####################################################
        if verbose:
            strg = "Transform date -> timelapse"
            color_print(strg)

        if len(self.d_features['date']) > 0:
            date_encoder = DateEncoder(method='timedelta')
            date_encoder.fit(df_local, l_var=self.d_features['date'], verbose=verbose)
            df_local = date_encoder.transform(df_local, verbose=verbose)
        else:
            "no features identified as dates"

        ##################
        # fill NA values
        ##################
        # num features
        if verbose:
            color_print('Fill NA')

        NA_encoder = NAEncoder()
        NA_encoder.fit(df_local, l_var=self.d_features['NA'], verbose=verbose)
        df_local = NA_encoder.transform(df_local, verbose=verbose)

        ####################
        # replace outliers
        ####################
        if process_outliers:
            out_encoder = OutliersEncoder()
            print('fit')
            out_encoder.fit(df_local, l_var=None, verbose=verbose)
            print('transform')
            df_local = out_encoder.transform(df_local, verbose=verbose)

        #########################
        # categorical processing
        #########################
        if verbose:
            color_print('Categorical and boolean features processing')

        cat_col = self.d_features['categorical'] + self.d_features['boolean']
        if self.target in cat_col:
            cat_col.remove(self.target)

        if len(cat_col) > 0:
            cat_encoder = CategoricalEncoder(method=cat_method)
            cat_encoder.fit(df_local, l_var=cat_col, target=self.target, verbose=verbose)
            df_local = cat_encoder.transform(df_local, verbose=verbose)

        self.__dict__.update(df_local.__dict__)
        self.target = target
        self.step = 'preprocess'

        if verbose:
            color_print("\nNew DataFrame size ")
            print("  > row number : ", self.shape[0], "\n  > col number : ", self.shape[1])

    """
    --------------------------------------------------------------------------------------------------------------------
    """

    @timer
    def select_features(self, method='pca', verbose=False):
        """Select features to speed up modelisation.
        (May incresea model performance aswell)

        Available methods : pca
        Parameters
        ----------
        method : string (Default : pca)
            method used to select features

        verbose

        Returns
        -------
            DataFrame : reduces datasset
        """
        assert self.step in ['preprocess'], 'apply preprocess method'
        target = self.target
        if verbose:
            print('')
            print_title1('Features Selection')
        df_local = self.copy()
        df_local = select_features(df=df_local, target=self.target, method=method, verbose=verbose)
        self.__dict__.update(df_local.__dict__)
        self.target = target
        self.step = 'features_selection'

    """
        --------------------------------------------------------------------------------------------------------------------
    """

    @timer
    def train_predict(self, clf='XGBOOST', metric='F1', n_comb=10, comb_seed=None, verbose=True):
        """Model hyper-optimisation with random search.

        - Create random hyper-parameters combinations from HP grid
        - train and test a model for each combination
        - get the best model in respect of a selected metric among valid model

        Available classifiers : Random Forest, XGBOOST (and bagging)

        Parameters
        ----------
        clf : string (Default : 'XGBOOST')
            classifier used for modelisation
        metric : string (Default : 'F1')
            objective metric
        n_comb : int (Default : 10)
            HP combination number
        comb_seed : int (Default : None)
            random combination seed
        verbose : boolean (Default False)
            Get logging information

        Returns
        -------
        dict
            {model_index : {'HP', 'probas', 'model', 'features_importance', 'train_metrics', 'metrics', 'output'}
        list
            valid model indexes
        int
            best model index
        DataFrame
            Models information and metrics stored in DataFrame
        """
        assert self.step in ['preprocess', 'features_selection'], 'apply preprocess method'

        if verbose:
            print('')
            print_title1('Train predict')

        # Train/Test split
        df_train, df_test = train_test(self, 0.3)

        # Create Hyperopt object
        hyperopt = Hyperopt(classifier=clf, grid_param=None, n_param_comb=n_comb,
                            top_bagging=False, comb_seed=comb_seed)

        # Entrainement des modèles
        if verbose:
            color_print('training models')
        hyperopt.fit(df_train, self.target, verbose=verbose)

        if verbose:
            color_print('\napplying models')
        # Application des modèles sur X_test :
        dict_res_model = hyperopt.predict(df_test, self.target, delta_auc=0.03, verbose=verbose)

        # selection best model
        if verbose:
            color_print('\nbest model selection')
        best_model_idx, l_valid_models = hyperopt.get_best_model(dict_res_model, metric=metric, delta_auc_th=0.03,
                                                                 verbose=False)

        df_model_res = hyperopt.model_res_to_df(dict_res_model, sort_metric=metric)

        if best_model_idx is not None:
            print_title1('best model : ' + str(best_model_idx))
            print(metric + ' : ' + str(round(dict_res_model[best_model_idx]['metrics'][metric], 4)))
            print('AUC : ' + str(round(dict_res_model[best_model_idx]['metrics']['Roc_auc'], 4)))

        return dict_res_model, l_valid_models, best_model_idx, df_model_res

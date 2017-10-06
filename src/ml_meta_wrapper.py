import numpy as np
import warnings
import time
import sys
from base import EnsembleBaseClassifier      
from importlib import import_module  
from operator import itemgetter
from numpy import random


class MetaWrapperClassifier():
    """
    Docstring:    
    Class that keeps track of available classifiers and implements functionality around them    
    Input:
    ------------------
       method = str: ('random' : Choose num_sample random classifiers (default),
                      'complete' : Choose all available classifiers,
                      'chosen' : Send in a list (iterable will work) of classifier names and initialize)                      
       num_sample: (int: 3) choose number of classifiers to sample. Used when method == 'random'
       estimators: (None or list/list-like: None): Send a list of classifiers to initialize. Used when method == 'chosen'
       base_estimator: (None or sklearn-type estimator: None) decide which classifier to use as a weak learner for ensemble methods
       verbose: (int, 0) if > 0 then be 'chatty'       
    Output:
    ------------------
    List of classifiers 
    """
    def __init__(self, method='random', num_sample=3, estimators=None, base_estimator=None, exclude=[], verbose=0):                    
        
        if method not in ('random', 'complete', 'chosen'):
            raise ValueError("'method' should be either ('random', 'complete', 'chosen').")                
        if method == 'chosen' and (estimators is None or len(estimators) == 0):
            suggestions = [name for name, _ in self.__build_classifier_repository()]
            raise ValueError("Specify name of at least one (1) classifier in list (iterable) 'clf'. \nValid options: %s" % suggestions)
            
        self.verbose = verbose   
        self.method = method
        self.num_sample = num_sample
        # This estimator is used as 'base_estimtor' in ensembling algorithms
        self.base_estimator = base_estimator
        self.exclude = exclude
        
        if method == 'chosen':
            self.clf = [(name, c) for name, c in self.__build_classifier_repository() if name in estimators]
        else:
            self.clf = self.__build_classifier_list()    
        self.clf = [(n, c) for n, c in self.clf if not (n in self.exclude)]               
        
        if self.verbose > 0:    
            print("Initialized classifiers: %s" % ", ".join(self.get_names()))         
    
    def get_names(self):
        return [name for name, _ in self.clf]
    
    def __build_classifier_list(self):
        clfs = self.__build_classifier_repository()        
        if self.method == 'random':
            print("Sampling %i algorithms..." % self.num_sample)
            clfs = [clfs[i] for i in random.choice(len(clfs), self.num_sample, replace=False)]        
        return clfs
        
    def __build_classifier_repository(self):
        """
        Return list of (classifier_name, classifier) tuples        
        """        
        # TODO: move this to a separate module containing algorithms only
        algorithms = [
            ('adaboost', 'MetaAdaBoostClassifierAlgorithm'), 
            ('nearest_neighbors', 'MetaKNearestNeighborClassifierAlgorithm'), 
            ('logistic_regression', 'MetaLogisticRegressionClassifierAlgorithm'),
            ('stochastic_gradient_descent', 'MetaSGDClassifierAlgorithm'),
            ('naive_bayes', 'MetaGaussianNBayesClassifierAlgorithm'),
            ('naive_bayes', 'MetaMultinomialNBayesClassifierAlgorithm'),
            ('naive_bayes', 'MetaBernoulliNBayesClassifierAlgorithm'),
            ('random_forest', 'MetaRandomForestClassifierAlgorithm'),
        ]        
        return [self._add_algorithm(m, c) for m, c in algorithms]

    def _add_algorithm(self, module_name, algorithm_name):                     
        try:
            module = import_module(module_name)
        except:
            raise ValueError("Could not import module '%s' (%s)" % (module_name, sys.exc_info()[1]))
        algorithm = getattr(module, algorithm_name)

        if issubclass(algorithm, EnsembleBaseClassifier):
            instance = algorithm(base_estimator=self.base_estimator)
        else:
            instance = algorithm()
        return instance.name, instance
    
    def fit_classifiers(self, X, y, n_jobs=1):
        for name, clf in self.clf:
            try:
                clf.estimator.set_params(**{'n_jobs': n_jobs})
            except:
                pass
            st = time.time()
            clf.estimator.fit(X, y)
            if self.verbose > 0:
                print("Classifier %s trained (time: %.2f min)" % (name, (time.time()-st)/60.))
        return
    
    def predict_classifiers(self, X):
        return [(name, clf.estimator.predict(X)) for name, clf in self.clf]
    
    def predict_proba_classifiers(self, X):
        probas = []
        for name, clf in self.clf:
            # Check if classifier implements 'predict_proba'
            d = clf.get_info()
            if d['predict_probas']:
                probas.append((name, clf.estimator.predict_proba(X)))
        return probas
    
    def classifier_performance(self, preds, y_true, metric='accuracy', multiclass=False, **kwargs):
        """
        **kwargs gives us the possibility to send extra parameters when computing various metrics        
        """
        from sklearn.metrics import accuracy_score, roc_auc_score, f1_score, recall_score, precision_score, log_loss
        
        # List of supported metric names and the corresponding method (tuples)
        metrics = [('accuracy', accuracy_score),
                   ('auc', roc_auc_score),
                   ('f1', f1_score),
                   ('recall', recall_score),
                   ('precision', precision_score),
                   ('log_loss', log_loss),]
        metrics_names = [f for f, _ in metrics]
        
        if not metric in metrics_names:
            raise ValueError("'metric' should be one of the following: '%s'" % ", ".join(metrics_names))
        scorer = [sc for name, sc in metrics if name == metric][0]
        scores = []
        
        for name, y_pred in preds:
            val = scorer(y_true, y_pred)
            if multiclass and len(np.array(y_pred).shape) == 1:
                from sklearn.preprocessing import LabelBinarizer
                lb = LabelBinarizer()
                yhat = lb.fit_transform(y_pred)
            else:
                yhat = np.array(y_pred)
            loss = log_loss(y_true, yhat)            
            scores.append((name, val, loss))                        
        scores.sort(key=itemgetter(1), reverse=True)
        
        if self.verbose > 0:
            for name, met, loss in scores: print("log_loss: %.4f \t %s: %.4f \t %s" % (loss, metric, met, name))
        return scores
    
    def optimize_classifiers(self, X, y, n_iter=12, scoring='accuracy', cv=10, n_jobs=1, 
                             sample_hyperparams=False, min_hyperparams=2, get_hyperparams=False, random_state=None):
        """
        Docstring:        
        This method is a wrapper to cross validation using RandomizedSearchCV from scikit-learn, wherein we optimize each defined algorithm
        Default behavior is to optimize all parameters available to each algorithm, but it is possible to sample (randomly) a subset of them
        to optimize (sample_hyperparams=True), or to choose a set of parameters (get_hyperparams=True).
        
        Input parameters:
        ------------------
        X: data matrix (n_samples, n_features)
        y: labels/ground truth (n_samples,)
        
        n_iter: (int: 1) number of iterations to use in RandomizedSearchCV method, i.e. number of independent draws from parameter dictionary
        scoring: (str or callable: 'accuracy') type of scorer to use in optimization
        cv: (int or callable: 10) number of cross validation folds, or callable of correct type
        n_jobs: (int: 1) specify number of parallel processes to use
        
        sample_hyperparams: (bool: False) randomly sample a subset of algorithm parameters and tune these  
        min_hyperparams: (int: 2) when sample_hyperparams=True, choose number of parameters to sample
        get_hyperparams: (bool: False) instead of random sampling, use previously chosen set of parameters to optimize (must be preceeded by ...)
        random_state: (None or int: None) used for reproducible results
        
        Ouput:
        ------------------
        List containing (classifier name, most optimized classifier) tuples       
        """
        from sklearn.model_selection import RandomizedSearchCV
        
        def _random_grid_search(p_index, clf, clf_name, param_dict):
            clf_name = clf_name + "_pd%i" % (p_index+1) if p_index > 0 else clf_name

            if sample_hyperparams and not get_hyperparams:
                num_params = np.random.randint(min_hyperparams, len(param_dict))
                param_dist = clf.sample_hyperparams(param_dict, num_params = num_params, mode = 'random')

            if get_hyperparams and not sample_hyperparams:
                if len(clf.cv_params_to_tune)>0:                    
                    param_dist = clf.sample_hyperparams(param_dict, keys = clf.cv_params_to_tune, mode = 'select')            

            n_iter_ = min(n_iter, clf.max_n_iter)        
            random_search = RandomizedSearchCV(clf.estimator, param_distributions=param_dict, n_iter=n_iter_, scoring=scoring, cv=cv, n_jobs=n_jobs, 
                                               verbose=self.verbose, error_score=0, return_train_score=True, random_state=random_state)
            start_time = time.time()
            try:
                random_search.fit(X, y)
            except:
                return (clf_name, clf.estimator.fit(X,y))
            else:
                return (clf_name, random_search.best_estimator_)            
            finally:
                if self.verbose > 0:
                    print("Search time = %.2f min." % ((time.time()-start_time)/60.))

        return [_random_grid_search(idx, clf, name, param_dict) for name, clf in self.clf for idx, param_dict in enumerate(clf.cv_params)]

    def bayesian_optimization(self, X, y, n_iter=100, scoring='accuracy', greater_is_better=True, cv=10, n_jobs=1):
        """
        Docstring:
        Use package 'scikit-optimize' >=0.3 in order to do Bayesian optimization instead of random grid search.
        Package URL: https://github.com/scikit-optimize/scikit-optimize/        
        """        
        from skopt import gp_minimize
        from utils import skopt_space_mapping        
        from sklearn.model_selection import cross_val_score
        
        skopt_spaces = skopt_space_mapping([(nm, cl.cv_params) for nm, cl in self.clf])        
        for name, classifier in self.clf:            
            # Define search space
            space = [(nm, skopt_space) for nm, skopt_space in skopt_spaces if nm==name]            
            if not isinstance(space[0], tuple) and (len(space)==1):
                raise ValueError("space object should have 1 element. Got: %s" % str(space))
            _, space = space[0]
            param_names = [nm for nm, _ in space.items()]
            space = [dimension for _, dimension in space.items()]
            
            # Define objective function (it will have access to externally defined variables in 
            # the calling method namespace
            def objective(params):
                param_dict = {param_name:param for param_name, param in zip(param_names, params)}                
                classifier.estimator.set_params(**param_dict) 
                score = np.mean(cross_val_score(classifier.estimator, X, y, cv=10, scoring='accuracy', n_jobs=-1))
                if greater_is_better:
                    return -score
                else:
                    return score
                
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                res_gp = gp_minimize(objective, space, n_calls=50, random_state=0)               
            print("Best score=%.4f (%s)" % (res_gp.fun, name))        
        return
    
class CheckClassifierCorrelation():
    """
    Check correlation between classifier predictions using e.g. Pearson's formula. Initially, a repository
    of classifiers is constructed from either a random, complete, or chosen selection (set by the 'method' parameter). 
    
    """
    def __init__(self, prediction_type=None):
        options = ('binaryclass', 'multiclass', 'regression')
        if prediction_type not in options:
            raise ValueError("Valid options for prediction_type are: %s" % ", ".join(options))            
        self.prediction_type = prediction_type
            
    def compute_correlation_matrix(self, preds):
        corr = np.zeros((len(preds), len(preds)), dtype=np.float32)
        names = []
        # Note that this is a bit "dodgy" for binary variables
        if self.prediction_type == 'binaryclass' or prediction_type == 'multiclass':
            from sklearn.metrics import matthews_corrcoef as mcc 
            for i, (nm1, y1) in enumerate(preds):
                names.append(nm1)
                for j, (nm2, y2) in enumerate(preds):
                    corr[i][j] = mcc(y1, y2)
        elif self.prediciton_type == 'regression':
            raise NotImplementedError("This method has not been implemented for regression yet.")           
        return names, corr
        
    def plot_correlation_matrix(self, names, corr, rot=0, fig_size=(9,9), font_scale=1.0, file=''):
        import seaborn as sns
        sns.set()
        from matplotlib import pyplot as plt
        
        f = plt.figure(figsize=fig_size)
        sns.set(font_scale=font_scale)
        sns.heatmap(corr, annot=True, fmt=".2f", cmap="YlGnBu", xticklabels=names, yticklabels=names)
        plt.xticks(rotation=90-rot)
        plt.tight_layout()
        if len(file)>0:
            print("Saving figure to '%s'" % file)
            try: 
                plt.savefig(file)
            except: 
                print("Could not save figure to %s." % file)
        return f  
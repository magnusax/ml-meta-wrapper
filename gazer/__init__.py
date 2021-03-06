import warnings

# Set version and author/email by hand
__version__ = '0.0.1'
__author__ = "Magnus Axelsson"
__email__ = "johanmagnusaxelsson<at>gmail<dot>com"


# Find external packages
def __checklib__(lib, alias):
    try:
        exec("import {}".format(lib))
        return True
    except:
        warnings.warn("""{} import failed; '{}' 
        will be unavailable.""".format(lib, alias), RuntimeWarning)
        return False
    
__importflags__ = [
    __checklib__(lib, alias) for lib, alias 
    in [('keras', 'neuralnet'), ('xgboost', 'xgboost')]]


# Once the flags are set, we can import package
from .core import GazerMetaLearner
from .ensembler import GazerMetaEnsembler


__all__ = [ "GazerMetaLearner", "GazerMetaEnsembler" ]
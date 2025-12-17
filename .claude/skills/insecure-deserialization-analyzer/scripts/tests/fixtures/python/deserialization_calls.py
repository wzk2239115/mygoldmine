"""
Test fixtures for Python deserialization vulnerabilities
"""

import pickle
import yaml
import dill
import cloudpickle
import marshal


# VULNERABLE: pickle.loads() with user input
def vulnerable_pickle_loads(data):
    return pickle.loads(data)


# VULNERABLE: pickle.load() from file
def vulnerable_pickle_load(file_obj):
    return pickle.load(file_obj)


# VULNERABLE: yaml.load() without safe loader
def vulnerable_yaml_load(data):
    return yaml.load(data)


# VULNERABLE: yaml.unsafe_load()
def vulnerable_yaml_unsafe_load(data):
    return yaml.unsafe_load(data)


# VULNERABLE: dill.loads() - can execute arbitrary code
def vulnerable_dill_loads(data):
    return dill.loads(data)


# VULNERABLE: cloudpickle.loads()
def vulnerable_cloudpickle_loads(data):
    return cloudpickle.loads(data)


# VULNERABLE: marshal.loads()
def vulnerable_marshal_loads(data):
    return marshal.loads(data)


# VULNERABLE: shelve operations
def vulnerable_shelve_open(filename):
    import shelve
    return shelve.open(filename)


# VULNERABLE: yaml with user input
class UserDataProcessor:
    def process(self, user_input):
        # This is vulnerable
        config = yaml.load(user_input, Loader=yaml.Loader)
        return config


# SEMI-VULNERABLE: yaml.full_load (safer but still has risks)
def semi_vulnerable_yaml_full_load(data):
    return yaml.full_load(data)


# SAFE: Using safe_load
def safe_example(data):
    return yaml.safe_load(data)


# SAFE: Using pickle with restricted unpickler
def safe_pickle_example(data):
    import io
    from pickle import Unpickler
    f = io.BytesIO(data)
    return Unpickler(f).load()

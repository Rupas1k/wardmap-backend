from .logging_config import build_logging_config

bind = "0.0.0.0:5000"
workers = 2
threads = 2
worker_class = "gthread"
accesslog = "-"
errorlog = "-"
capture_output = True
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(L)ss'
logconfig_dict = build_logging_config()

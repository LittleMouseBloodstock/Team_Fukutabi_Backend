import sys
print('sys.path[0]=', sys.path[0])
import google
print('google:', getattr(google, '__file__', None), getattr(google, '__path__', None))
try:
    import google.cloud
    print('google.cloud:', getattr(google.cloud, '__file__', None), getattr(google.cloud, '__path__', None))
except Exception as e:
    print('import google.cloud failed:', e)

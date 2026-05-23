from config import manager
from toolbox import ToolBox
from pprint import pprint
from datetime import datetime

from call_agent import call_agent


res = call_agent("who is tinubu in nigeria", thread_id="50000")
print(res)


from config import manager
from toolbox import ToolBox
from pprint import pprint
from datetime import datetime


  
  
tools = manager.read_toolbox("what is the time now",1)

pprint(tools[0],indent=4)


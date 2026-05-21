from config.config import manager
from tools.toolbox import ToolBox
from pprint import pprint
from datetime import datetime


  
  
tools = manager.read_toolbox("what me about musk",1)

pprint(tools[0],indent=4)


""" 
All the configuration items for rFactory.
Some can be edited to change how rFactory works, e.g. the car table columns.

"""
# rF2 items
rF2root = r'C:\Program Files (x86)\Steam\steamapps\common\rFactor 2'
SteamExe = "C:/Program Files (x86)/Steam/steam.exe"

# General items

# Tags used by rFactory. Only some are present in rFactor files, 
# the rest are all included but may be blank
carTags = ['Manufacturer', 'Model', 'Class', 'tType', 'F/R/4WD', 
           'Year', 'Decade', 'Rating', 'DB file ID', 'Gearshift', 'Aids',
           'AIstrengthFactor', 'GraphicDetailsFactor', 'originalFolder', 'vehFile',
           # The standard ones we include:
           'Name','Version','Type','Author','Origin','Category',
           'ID','URL','Desc','Date','Flags','RefCount','MinVersion']
# Omit 'Signature','MASFile','BaseSignature'

trackTags = ['Track Name', 'Continent', 'Country', 'tType',
             'Year', 'Decade', 'Rating', 'DB file ID', 
             'AIstrengthFactor', 'GraphicDetailsFactor', 'originalFolder', 'Scene Description',
             # The standard ones we include:
             'Name','Version','Type','Author','Origin','Category',
             'ID','URL','Desc','Date','Flags','RefCount','MinVersion']

CarDatafilesFolder = 'CarDatafiles'
TrackDatafilesFolder = 'TrackDatafiles'
dataFilesExtension = '.rFactory.txt'

# File-specific items
config_tabCar = {
  'carColumns' : ['Manufacturer', 'Model', 'Class', 'Author', 'tType', 
                  'F/R/4WD', 'Year', 'Decade', 'Rating', 'vehFile','DB file ID'],
  'carFilters' : ['Manufacturer', 'Model', 'Class', 'Author', 'tType', 
                  'F/R/4WD', 'Year', 'Decade', 'Rating', 'vehFile']
  }

config_tabTrack = {
  'trackColumns' : ['Track Name', 'Version', 'Continent', 'Country', 'Author', 'tType', 
                  'Year', 'Decade', 'Rating', 'Scene Description','DB file ID'],
  'trackFilters' : ['Author', 'Continent', 'Country', 'tType','Year', 'Decade', 'Rating','Scene Description']
  }
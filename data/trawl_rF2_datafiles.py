"""
Trawl rF2 data files for raw data as a baseline for rFactory data files
1) find files
2) read them
3) grep for data keywords
4) Title Case them
5) extract data into data file

6) check if rF2 data file has been deleted
"""

import datetime
import os
import re
import subprocess
import time

import tkinter as tk
from tkinter import ttk
from tkinter import messagebox

from data.rFactoryConfig import rF2root,carTags,trackTags,CarDatafilesFolder, \
  TrackDatafilesFolder,dataFilesExtension,playerPath,markerfileExtension
from data.utils import getListOfFiles, readFile, writeFile, getTags

from data.rFactoryData import getSingleCarData, reloadAllData
from data.LatLong2Addr import google_address, country_to_continent
from data.cached_data import Cached_data

import edit.carNtrackEditor as carNtrackEditor

def trawl_for_new_rF2_datafiles(parentFrame):
  filesToDelete = listDeletedDataFiles()
  if len(filesToDelete):
    delete = messagebox.askyesno(
              'Scanned rFactory data files',
              'rFactory data files out of date:\n%s\nDo you want to delete them?\n' % '\n'.join(filesToDelete)
          )
    if delete:
      for file in filesToDelete:
        os.remove(file)

  newFiles = createDefaultDataFiles(overwrite=False)
  reloadAllData()
  if len(newFiles):
    if len(newFiles) < 10:    # if there are too many forget it
      edit = messagebox.askyesno(
                'Scanned rF2 data files',
                'New rFactory data files created:\n%s\nDo you want to edit them now?\n' % '\n'.join(newFiles)
            )
    else:
      messagebox.askokcancel(
                'Scanned rF2 data files',
                '%s new rFactory data files created. Edit them at some time.\n' % len(newFiles)
            )
      edit = False
    if edit:
      for newFile in newFiles:
        root = tk.Tk()
        tabTrack = ttk.Frame(root, width=1200, height=600, relief='sunken', borderwidth=5)
        root.title('Editor')
        tabTrack.grid()

        fields = carTags
        data = getSingleCarData(id=newFile, tags=fields)
        o_tab = carNtrackEditor.Editor(tabTrack, fields, data, DatafilesFolder=CarDatafilesFolder)
        tk.mainloop()
  return newFiles



carCategories = {
  '3' : 'GT',
  '5' : 'Novel',
  '6' : 'Open',
  '7' : 'Prototype',
  '9' : 'Street',
  '10' : 'Touring'
  }

trackCategories = {
  '53' : 'Novel',
  '55' : 'Permanent',
  '56' : 'Rally',
  '57' : 'Temporary'
  }

def createDataFile(datafilesPath, filename, dict, tagsToBeWritten, overwrite=False):
  _filepath = os.path.join(datafilesPath, filename+dataFilesExtension)
  _newFile = False
  if overwrite or not os.path.exists(_filepath):
    try:
      os.makedirs(datafilesPath, exist_ok=True)
      with open(_filepath, "w") as f:
        for tag in tagsToBeWritten:
          if tag in dict:
            val = dict[tag]
            if tag == 'Date':
              if len(val) == 18: # Windows filetime.
                # http://support.microsoft.com/kb/167296
                # How To Convert a UNIX time_t to a Win32 FILETIME or SYSTEMTIME
                EPOCH_AS_FILETIME = 116444736000000000  # January 1, 1970 as MS file time
                HUNDREDS_OF_NANOSECONDS = 10000000
                ts = datetime.datetime.fromtimestamp((int(val) - EPOCH_AS_FILETIME) //
                                                    HUNDREDS_OF_NANOSECONDS)
              else: # Unix
                ts = datetime.datetime.fromtimestamp(int(val))
              val = ts.strftime("%Y-%m-%d")
          elif tag == 'DB file ID':
            val = filename # The unique identifier for the car/track. I think.
          elif tag in ['Track Name', 'Manufacturer', 'Model']:
            val = dict['strippedName'].replace('_', ' ').strip()  # default
            if val.startswith('Isi'):
              val = val[4:]
            if val.startswith('Ngtc'):
              val = val[5:]
            if not val == '':
              if tag == 'Manufacturer':
                val = val.split()[0]
                # Fix case issues:
                _mfrs = {'Ac':'AC', 'Ats':'ATS', 'Alfaromeo': 'Alfa Romeo', 'Brm':'BRM', 'Bmw':'BMW', 'Mclaren':'McLaren'}
                if val in _mfrs:
                  val = _mfrs[val]
              if tag == 'Model' and len(val.split()) > 1:
                val = ' '.join(val.split()[1:])
          elif tag == 'Rating':
            val = '***'
          elif tag == 'Gearshift':
            val = 'Paddles' # a reasonable default
          else: # value not available
            val = ''
          f.write('%s=%s\n' % (tag, val))
      _newFile = True
    except OSError:
      print('Failed to write %s' % _filepath)
      quit()
    except Exception as e:
      print(e)
      quit()
  return _newFile

def cleanTrackName(name):
  """ Track names often include a version, strip that """
  name = re.sub(r'v\d+\.\d*', '', name)
  return name

def extractYear(name):
  # Cars and tracks often include the year, try to extract that.
  # Also return remainder of name when year removed.
  # skip first digit, may be 3PA....
  if name.startswith('3'):
    name = name[1:]
  year = ''
  decade = ''
  # Look for 4 digit years first to avoid BT44
  # Reverse as the year tends to be at the end, e.g. USF2000_2016
  _years = re.findall(r'(\d+)', name)
  if _years:
    _years.reverse()
    for y in _years:
      if len(y) == 4:
        year = y
        decade = year[:3] + '0-'
        #print(name, year)
        return year, decade, name.replace(y,'')
    for y in _years:
      if len(y) == 2:
        if y[0] in '01':
          year = '20' + y
        else:
          year = '19' + y
        decade = year[:3] + '0-'
        return year, decade, name.replace(y,'')
  #print(name, year)
  return year, decade, name

class vehFiles:
  #[VEHICLE]
  #ID=1
  #File="%ProgramFiles(x86)%\Steam\steamapps\common\rFactor 2\Installed\Vehicles\AC_427SC_1967\1.2\427SC_BLACK.VEH"
  #...

  vehDict = {}
  def __init__(self):
    self.all_vehicles_ini = os.path.join(playerPath, 'all_vehicles.ini')
    all_vehicles_text = readFile(self.all_vehicles_ini)
    for line in all_vehicles_text:
      if line.startswith('File='):
        _path, _veh = os.path.split(line[len('File="'):])
        _path, _rev = os.path.split(_path)
        _path, _car = os.path.split(_path)
        if not _car in self.vehDict:
          self.vehDict[_car] = _veh.strip()[:-1]  # lose the trailing "
  #@property
  def veh(self, carName) :
    try:
      return self.vehDict[carName]
    except:
      print('%s not in %s' % (carName, self.all_vehicles_ini))
    return ''


def getVehScnNames(dataFilepath):
  """
  Read the data file containing Name xxxxx.veh pairs
  Also for xxxxx.scn pairs
  """
  _dict = {}
  text = readFile(dataFilepath)
  for line in text:
    if line.startswith('#'):
      continue # comment line
    _split = line.split()
    if len(_split) == 2:
      name, vehScn = _split
      _dict[name] = vehScn
  return _dict

def createDefaultDataFiles(overwrite=False):
  newFiles = []
  getAllTags = False
  rF2_dir = os.path.join(rF2root, 'Installed')
  vehicleFiles = getListOfFiles(os.path.join(rF2_dir, 'vehicles'), pattern='*.mft', recurse=True)
  trackFiles = getListOfFiles(os.path.join(rF2_dir, 'locations'), pattern='*.mft', recurse=True)
  F1_1988_trackFiles = getListOfFiles(os.path.join(rF2_dir, 'locations', 'F1_1988_Tracks'), pattern='*.mas', recurse=True)
  cache_o = Cached_data()
  cache_o.load()

  #vehNames = getVehScnNames('vehNames.txt')
  vehNames = vehFiles()

  tags = {}
  if getAllTags:
    for veh in vehicleFiles:
      text = readFile(veh[0])
      for tag in readTags(text):
        tags[tag] = 0
    #print(tags)
  else: # create data file
    for veh in vehicleFiles:
      text = readFile(veh[0])
      tags = getTags(text)
      #print('\nData file: "%s.something"' % tags['Name'])
      for requiredTag in ['Name','Version','Type','Author','Origin','Category','ID','URL','Desc','Date','Flags','RefCount','#Signature','#MASFile','MinVersion','#BaseSignature']:
        # MASFile, Signature and BaseSignature filtered out - NO THEY AREN'T,
        # tags[] still contains them.  tagsToBeWritten filters them out.
        # Not sure what this for loop is, er, for.
        if requiredTag in tags:
          """filter out boilerplate
          Author=Mod Team
          URL=www.YourModSite.com
          Desc=Your new mod.
          """
          if tags[requiredTag] in ['Mod Team', 'www.YourModSite.com', 'Your new mod.']:
            tags[requiredTag] = ''
          if tags[requiredTag] in ['Slow Motion', 'Slow Motion Modding Group']: # make up your minds boys!
            tags[requiredTag] = 'Slow Motion Group'
          if tags[requiredTag] in ['Virtua_LM Modding Team']: # make up your minds boys!
            tags[requiredTag] = 'Virtua_LM'
          #print('%s=%s' % (requiredTag, tags[requiredTag]))
          if requiredTag == 'Name':
            tags['Year'], tags['Decade'], tags['strippedName'] = extractYear(tags['Name'])
            # extract class from name if it's there
            for __class in ['F1', 'F3', 'GT3', 'GTE', 'BTCC', 'LMP1', 'LMP2', 'LMP3']: # 'F2' filters rF2...
              if __class in tags['Name']:
                tags['Class'] = __class
                tags['strippedName'] = tags['strippedName'].replace(__class, '')
            tags['strippedName'] = tags['strippedName'].title() # Title Case The Name
      if tags['Category'] in carCategories:
        tags['tType'] = carCategories[tags['Category']]
      # We need the original data folder to assemble the .VEH file path to put in
      # "All Tracks & Cars.cch" to force rF2 to switch cars.  We also need the .VEH
      # file names and that's a bit more difficult.
      # Not difficult, they're in all_vehicles.ini
      tags['originalFolder'], _ = os.path.split(veh[0][len(rF2root)+1:]) # strip the root
      # if veh file name is available in vehNames.txt use it
      tags['vehFile'] = vehNames.veh(tags['Name'])

      cached_tags = cache_o.get_values(tags['Name'])
      cache_write = False
      if not cached_tags:
          # We don't already have data scanned from MAS files

          __scn, mas_tags = getMasInfo(
                os.path.join(rF2root, tags['originalFolder']))
          if 'SemiAutomatic' in mas_tags:
              if mas_tags['SemiAutomatic'] == '0':
                tags['Gearshift'] = 'H' + mas_tags['ForwardGears']
              else: # Paddles or sequential
                tags['Gearshift'] = 'Paddles'
          if 'WheelDrive' in mas_tags:
                tags['F/R/4WD'] = mas_tags['WheelDrive']
          tags['Aero'] = 1
          if 'FWSetting' in mas_tags and 'RWSetting' in mas_tags:
                if mas_tags['FWSetting'] == '0' and mas_tags['RWSetting'] == '0':
                    tags['Aero'] = 0
          if 'DumpValve' in mas_tags:
                tags['Turbo'] = '1'
          else:
                tags['Turbo'] = '0'
          if 'Mass' in mas_tags:
                tags['Mass'] = int(mas_tags['Mass'].split('.')[0]) # May be float
          else: # that probably indicates that mas was encrypted => S397
                tags['Mass'] = ''
                if tags['Author'] == '':
                    tags['Author'] = 'Studio 397?'
                if not 'Gearshift' in tags or tags['Gearshift'] == '':
                    tags['Gearshift'] = 'Paddles'
                if not 'F/R/4WD' in tags or tags['F/R/4WD'] == '':
                    tags['F/R/4WD'] = 'REAR'
          for tag in ['Gearshift','F/R/4WD','Aero','Turbo','Mass','Author']:
            if tag in tags:
              cache_o.set_value(tags['Name'], tag, tags[tag])
          cache_write = True


      for tag in tags:
        if cached_tags and tag in cached_tags:
          if cached_tags[tag] != '':
            # We have a cached tag for this one
            tags[tag] = cached_tags[tag]
          else:
            cache_o.set_value(tags['Name'], tag, tags[tag])
            cache_write = True

      if createDataFile(datafilesPath=CarDatafilesFolder,
                        filename=tags['Name'],
                        dict=tags,
                        tagsToBeWritten=carTags,
                        overwrite=overwrite):
        # a new file was written
        newFiles.append(tags['Name'])
  if cache_write:
      cache_o.write()

  #print('\n\nTracks:')
  tags = {}
  if getAllTags:
    for track in trackFiles:
      text = readFile(track[0])
      for tag in readTags(text):
        tags[tag] = 0
    #print(tags)
  else: # create data file
    for track in trackFiles:
      text = readFile(track[0])
      tags = getTags(text)
      if track[1] != 'F1_1988_Tracks.mft':
        _markerfilepath = os.path.join(TrackDatafilesFolder,
                                       tags['Name']+markerfileExtension)
        if overwrite or not os.path.exists(_markerfilepath):
          # Create a marker file with the overall name
          # otherwise this scans for SCN files every time
          createMarkerFile(_markerfilepath)
          scns = getScnFilenames(os.path.dirname(track[0]))
          if len(scns):
            for scn in scns:
              tags['Scene Description'] = scn
              tags['Name'] = scn
              newTrack = processTrack(track, tags)
              if newTrack:
                newFiles.append(newTrack)

          else:
            newTrack = processTrack(track, tags)
            if newTrack:
              newFiles.append(newTrack)

      else: # it's a folder of several tracks
        for track in F1_1988_trackFiles:
          tags['Name'] = track[1][:-4]
          _filepath = os.path.join(TrackDatafilesFolder, tags['Name']+dataFilesExtension)
          if overwrite or not os.path.exists(_filepath):
            tags['Scene Description'] = tags['Name']
            newTrack = processTrack(track, tags)
            if newTrack:
              newFiles.append(newTrack)
  return newFiles

def processTrack(track, tags):
  #print('\nData file: "%s.something"' % tags['Name'])
  cache_o = Cached_data()
  cache_o.load()

  for requiredTag in ['Name','Version','Type','Author','Origin','Category','ID','URL','Desc','Date','Flags','RefCount','#Signature','#MASFile','MinVersion','#BaseSignature']:
    # MASFile, Signature and BaseSignature filtered out
    if requiredTag in tags:
      """filter out boilerplate
      Author=Mod Team
      URL=www.YourModSite.com
      Desc=Your new mod.
      """
      if tags[requiredTag] in ['Mod Team', 'www.YourModSite.com', 'Your new mod.']:
        tags[requiredTag] = ''
      #print('%s=%s' % (requiredTag, tags[requiredTag]))
      if requiredTag == 'Name':
        tags['strippedName'] = cleanTrackName(tags['Name'])
        tags['Year'], tags['Decade'], tags['strippedName'] = extractYear(tags['strippedName'])
        tags['strippedName'] = tags['strippedName'].title() # Title Case The Name
  # We need the original data folder to assemble the .SCN file path to put in
  # "Player.JSON" to force rF2 to switch tracks.  We also need the .SCN
  # file names and that's a bit more difficult.
  # To select the track we also need the "Scene Description"
  tags['originalFolder'], _ = os.path.split(track[0][len(rF2root)+1:]) # strip the root
  if not 'Scene Description' in tags or tags['Scene Description'] == '':
    # if scn file name is available in scnNames.txt use it
    scnNames = getVehScnNames('scnNames.txt')
    if tags['Name'] in scnNames:
      tags['Scene Description'] = scnNames[tags['Name']]

  if tags['Category'] in trackCategories:
    tags['tType'] = trackCategories[tags['Category']]

  cached_tags = cache_o.get_values(tags['Name'])
  cache_write = False

  if not cached_tags or cached_tags['Country'] == '':
    __scn, mas_tags = getMasInfo(
        os.path.join(rF2root, tags['originalFolder']))
    if 'Latitude' in mas_tags and 'Longitude' in mas_tags:
        lat = float(mas_tags['Latitude'])
        long = float(mas_tags['Longitude'])
        address_o = google_address(lat, long)

        tags['Country'] = address_o.get_country()
        tags['Continent'] = country_to_continent(tags['Country'])

  for tag in tags:
    if cached_tags and tag in cached_tags:
      if cached_tags[tag] != '':
        # We have a cached tag for this one
        tags[tag] = cached_tags[tag]
    else:
        cache_o.set_value(tags['Name'], tag, tags[tag])
        cache_write = True

  if cache_write:
      cache_o.write()

  if createDataFile(datafilesPath=TrackDatafilesFolder,
                    filename=tags['Name'],
                    dict=tags,
                    tagsToBeWritten=trackTags):
    # a new file was written
    return tags['Name']
  return None

def createMarkerFile(filepath):
  """ Create a file to mark that a track folder has been processed """
  writeFile(filepath,
            'This marks that the track folder has been processed.\n'
            'No need to scan for SCN files again.')

def listDeletedDataFiles():
  newFiles = []
  rF2_dir = os.path.join(rF2root, 'Installed')
  rFactoryVehicleFiles = getListOfFiles('CarDatafiles',
                                        pattern='*.txt', recurse=False)
  rFactoryTrackFiles = getListOfFiles('TrackDatafiles',
                                      pattern='*.txt', recurse=False)

  filesToDelete = []
  for car in rFactoryVehicleFiles:
    _data = readFile(car[0])
    for line in _data:
      if line.startswith('originalFolder'):
        _f = line[len('originalFolder='):-1]
        if not os.path.isdir(os.path.join(rF2root, _f)):
          filesToDelete.append(car[0])
  for track in rFactoryTrackFiles:
    _data = readFile(track[0])
    for line in _data:
      if line.startswith('originalFolder'):
        _f = line[len('originalFolder='):-1]
        if not os.path.isdir(os.path.join(rF2root, _f)):
          filesToDelete.append(track[0])
  return filesToDelete

def getScnFilenames(folder):
  # Could also use this to get .veh filenames for cars.
  ModMgr = os.path.join(rF2root, r'Bin32\ModMgr.exe')
  masFiles = getListOfFiles(folder, '*mas')
  all = []
  for mas in masFiles:
    """ Return nothing
    ls = subprocess.run([ModMgr, '-h'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(ls.stderr.decode('utf-8'))
    #_op = subprocess.run([ModMgr, '-l%s' % mas[1]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #So pipe to a file and read it
    """
    _pop = os.getcwd()  # save current directory
    os.chdir(os.path.dirname(mas[0]))
    #cmd = '"'+ModMgr + '" -l%s > temporaryFile 2>>errors' % mas[1]
    cmd = '"'+ModMgr + '" -q -l%s temporaryFile > nul 2>&1' % mas[1]
    os.system(cmd)
    lines = readFile('temporaryFile')
    for line in lines:
      if '.scn' in line.lower():
        all.append(line.strip()[:-4]) # Strip whitespace and .scn
      if 'unable to open package file' in line.lower():
        print(mas[1])
    try:
      os.remove('temporaryFile')
    except:
      pass # No SCN files in MAS files
    os.chdir(_pop)
  return all


def getMasInfo(folder):
  """
  Open the mas files and look for
  *.hdv
    ForwardGears=6
    WheelDrive=REAR // which wheels are driven: REAR, FOUR, or FRONT
    SemiAutomatic=0 // whether throttle and clutch are operated automatically (like an F1 car)

    maybe:
    TCSetting=0 ????
    TractionControlGrip=(1.4, 0.2)    // average driven wheel grip multiplied by 1st number, then added to 2nd
    TractionControlLevel=(0.33, 1.0)  // effect of grip on throttle for low TC and high TC
    ABS4Wheel=0                       // 0 = old-style single brake pulse, 1 = more effective 4-wheel ABS
    ABSGrip=(1.7, 0.0)                // grip multiplied by 1st number and added to 2nd
    ABSLevel=(0.31, 0.92)             // effect of grip on brakes for low ABS and high ABS
    Mass=828.0      Weight threshold
    FWRange=(0, 1, 1)             // front wing range
    FWSetting=0                   // front wing setting
    RWRange=(0, 1, 1)             // rear wing range
    RWSetting=0                   // rear wing setting

  (engine)*.ini
    BoostPower=0 no turbo?
    DumpValve=
    Turbo*


  """

  hdv_keywords = [
      'ForwardGears',
      'WheelDrive',
      'SemiAutomatic',
      'Mass',
      'FWSetting',
      'RWSetting'
      ]

  ini_keywords = [
      'DumpValve',
      'Turbo'
      ]

  gdb_keywords = [
      'Latitude',
      'Longitude'
      ]

  ModMgr = os.path.join(rF2root, r'Bin32\ModMgr.exe')
  masFiles = getListOfFiles(folder, '*mas')
  all = []
  mas_dict = {}
  circuit_dict = {}
  for mas in masFiles:
    """ Return nothing
    ls = subprocess.run([ModMgr, '-h'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(ls.stderr.decode('utf-8'))
    #_op = subprocess.run([ModMgr, '-l%s' % mas[1]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #So pipe to a file and read it
    """
    _pop = os.getcwd()  # save current directory
    os.chdir(os.path.dirname(mas[0]))
    #cmd = '"'+ModMgr + '" -l%s > temporaryFile 2>>errors' % mas[1]
    cmd = '"'+ModMgr + '" -q -l%s 2>&1 temporaryFile > nul 2>&1' % mas[1]
    os.system(cmd)
    lines = readFile('temporaryFile')
    for line in lines:
      if '.scn' in line.lower():
        all.append(line.strip()[:-4]) # Strip whitespace and .scn
      if 'unable to open package file' in line.lower():
        print(mas[1])
      line = line.strip()
      if '.hdv' in line.lower():
          cmd = '"'+ModMgr + '" -q -x%s %s > nul 2>&1' % (mas[1], line)
          os.system(cmd)
          hdv_lines = readFile(line)
          for hdv_line in hdv_lines:
              hdv_line = hdv_line.strip()
              for kw in hdv_keywords:
                  if hdv_line.startswith(f'{kw}='):
                      mas_dict[kw]=re.split('[= /\t]+', hdv_line)[1].strip()
          try:
            os.remove(line)   # delete extracted file
          except:
            print('Failed to extract %s from %s' % (line, mas[1]))
      if '.ini' in line.lower():
          cmd = '"'+ModMgr + '" -q -x%s %s > nul 2>&1' % (mas[1], line)
          os.system(cmd)
          ini_lines = readFile(line)
          for ini_line in ini_lines:
              ini_line = ini_line.strip()
              for kw in ini_keywords:
                  if ini_line.startswith(f'{kw}'):
                      mas_dict[kw]=re.split('[= /\t]+', ini_line)[1].strip()
          try:
            os.remove(line)   # delete extracted file
          except:
            print('Failed to extract %s from %s' % (line, mas[1]))
            pass # ini file name has spaces?
      if '.gdb' in line.lower():
          cmd = '"'+ModMgr + '" -q -x%s %s > nul 2>&1' % (mas[1], line)
          os.system(cmd)
          gdb_lines = readFile(line)
          for gdb_line in gdb_lines:
              gdb_line = gdb_line.strip()
              for kw in gdb_keywords:
                  if gdb_line.startswith(f'{kw}'):
                      mas_dict[kw]=re.split('[= /\t]+', gdb_line)[1].strip()
          try:
            os.remove(line)   # delete extracted file
          except:
            print('Failed to extract %s from %s' % (line, mas[1]))
    try:
      os.remove('temporaryFile')
    except:
      pass # No SCN files in MAS files
    os.chdir(_pop)
  return all, mas_dict



if __name__ == '__main__':
  root = tk.Tk()
  tabCar = ttk.Frame(root, width=1200, height=1200, relief='sunken', borderwidth=5)
  tabCar.grid()

  scns = getScnFilenames(r"c:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Installed\Locations\BATHURST_2016_V3\3.0" )

  #createDefaultDataFiles(overwrite=True)
  newFiles = trawl_for_new_rF2_datafiles(root)
  #if newFiles != []:
  #  root.mainloop()

  rF2_dir = r"c:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Installed"
  vehicleFiles = getListOfFiles(os.path.join(rF2_dir, 'vehicles'), pattern='*', recurse=False)

  car_scn, mas_dict = getMasInfo(r"c:\Program Files (x86)\Steam\steamapps\common\rFactor 2\Installed\Vehicles\ferrari_312_67\1.2")
  print(mas_dict)

  for vehicleFile in vehicleFiles:
      folder = getListOfFiles(vehicleFile[0], pattern='*')[0][0]
      car_scn, mas_dict = getMasInfo(folder)
      print(mas_dict)

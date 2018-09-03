#!/usr/bin/env python3

import json
import requests
import io
import os
import configparser
import datetime
import time
from oauth2client import file, client, tools
import tkinter
from tkinter import filedialog
from functools import partial

# Ce script permet d'uploader un fichier vers Google Drive en utilisant l'API.
# L'intérêt de ce script réside dans le fait qu'il permet de reprendre un upload
#  qui a été intérrompu suite à une perte de connexion, ou un plantage du PC durant le transfert, 
#  en reprenant le transfert là où il s'était interrompu (sans recommencer le transfert depuis le début).
# 
# 2 fonctionnalités principales sont proposées : 
#   - Initier un nouvel upload
#   - Reprendre un upload interrompu

# Référence 
#   https://developers.google.com/drive/api/v3/resumable-upload
# Liste des paquets à installer pour exécuter le script
#   pip3 install --upgrade google-api-python-client oauth2client
#   pip3 install ConfigParser
#   apt-get install python3-tk
# Le script s'exécute en python3

# Quelques notions utilisées dans ce script : 
# La notion de "Pathfilename", c'est le nom complet (chemin + nom) du fichier à uploader
# La notion de "Filename", c'est le nom que portera le fichier une fois uploadé sur google drive
# La notion de "Token id", c'est le jeton d'autorisation de transfert vers google drive
#       Exemple de token id : ya29.GlsLBlLkXHs3dlGXNxmwRyY_NooOT0OvUsplMZ4043GO3Xqrs-e8eQz_KRfzZ47C176oD6Uq9EzxgQoJH8J_vWGHuZu4Q7orK7TpSMC_OKKhgCe4oUM2wx9-3ge2
# La notion de "Upload id", c'est un numéro unique renvoyé par google drive au début d'un upload. 
#       Cet identifiant permet de reprendre ultérieurement le téléchargement interrompu.
#       Exemple de upload id : AEnB2UqjQLzEOR9gDCBm5QEjlvL9a3f_HVh4iw-q9ApIl1i0z1SW0EYZoyLpqk9cW9ZefSkBV68tc2r2TDgjPEC1EawTRK4l0Q

# La première étape pour initier un upload est d'obtenir un jeton d'autorisation : c'est la notion de "Token ID"
#   https://developers.google.com/drive/api/v3/quickstart/python
#       1. Obtenir le fichier credential.json contenant identifiant/mot de passe pour l'accès à l'API
#       2. Le Token Id est obtenu automatiquement dans ce module par le point d'entrée getTokenId()
#          Une fois obtenu, ce token id a une durée limitée dans le temps et est disponible dans le fichier token.json
#   Le token id n'est nécessaire que pour initier un nouveau upload. Pour reprendre un upload qui a été interrompu
#    le token id n'est pas nécessaire
#   Pour obtenir un Token ID, il faut disposer d'un identifiant / mot de passe que l'on peut obtenir depuis :
#   

# Lorsqu'un nouvel upload est initié, les informations nécessaire pour reprendre le téléchargement sont mémorisées
#  automatiqment dans un fichier texte ".ini" dont le nom contient la date et l'heure.
# Pour une reprise du téléchargement interrompu, utiliser le point d'entrée qui récupère les information depuis un fichier
#  de configuration et poursui le téléchargement : resumeFromConfigFile(<nom fichier config>)
# 
# 
# Exemples : 
#  > Exemple n°1 : Commencer un nouveau transfert vers le drive
#       newResumableUpload(PAHTFILENAME, FILENAME, TOKEN_ID)

#  > Exemple n°2 : Reprendre un téléchargement interrompu à partir des données mémorisées dans un fichier de configuration
#       resumeFromConfigFile('upload_config_2018_09_01_16h54m44s.ini')

#  > Exemple n°3 : Vérifier si un téléchargement s'est terminé jusqu'au bout ou s'il est inachevé
#       _status, _start, _end = checkUploadComplete(UPLOAD_ID)

# L'interface utilisateur n'est réalisée que pour fournir les données nécessaire à l'exécution
# Tous les retours et messages sont réalisés dans la console

CHUNK_SIZE = (1024 * 1024 * 4) # Size of each packet of the file sent in the resumable multiple chunks mode

verbose = True

# =================================================================
# GUI
# =================================================================
# __________________________________________________________________
# Les callbacks
def cb_getTokenId(root):
    _token_id = createTokenId()
    root.text_token_id.set(_token_id)

def cb_selectPathfileName(root):
    root.pathfilename =  tkinter.filedialog.askopenfilename(initialdir = "/home",title = "Select file",filetypes = (("all files","*.*"), ("all files","*.*")))
    root.text_pathfilename.set(root.pathfilename)
    root.text_filename.set(os.path.basename(root.pathfilename))

def cb_startNewUpload(root):
    if (root.text_token_id.get() == ""):
        cb_getTokenId(root)
    newResumableUpload(root.text_pathfilename.get(), root.text_filename.get(), root.text_token_id.get())

def cb_loadConfigFile(root):
    _configPathfilename =  tkinter.filedialog.askopenfilename(initialdir = "/home",title = "Select file",filetypes = (("all files","*.ini"), ("all files","*.ini")))
    _pathfilename, _filename, _upload_id = readConfigFile(_configPathfilename)
    root.text_pathfilename.set(_pathfilename)
    root.text_filename.set(_filename)
    root.text_upload_id.set(_upload_id)

def cb_resumeUpload(root):
    resumeExistingUpload(root.text_pathfilename.get(), root.text_filename.get(), root.text_upload_id.get())

# __________________________________________________________________
# Création de l'interface utilisateur
def createGui(root):
    root.text_token_id = tkinter.StringVar(root)
    root.label_token_id = tkinter.Label(root, text='Token ID')
    root.entry_token_id = tkinter.Entry(root, textvariable=root.text_token_id)
    root.button_token_id = tkinter.Button(root, text='new', command=partial(cb_getTokenId, root))

    root.text_pathfilename = tkinter.StringVar(root)
    root.label_pathfilename = tkinter.Label(root, text='Pathfilename')
    root.entry_pathfilename = tkinter.Entry(root, textvariable=root.text_pathfilename)
    root.button_pathfilename = tkinter.Button(root, text='...', command=partial(cb_selectPathfileName, root))

    root.text_filename = tkinter.StringVar(root)
    root.label_filename = tkinter.Label(root, text='Filename')
    root.entry_filename = tkinter.Entry(root, textvariable=root.text_filename)

    root.text_upload_id = tkinter.StringVar(root)
    root.label_upload_id = tkinter.Label(root, text='Upload_id')
    root.entry_upload_id = tkinter.Entry(root, textvariable=root.text_upload_id)

    root.button_loadConfigFile = tkinter.Button(root, text='Load Config File', command=partial(cb_loadConfigFile, root))
    root.button_startNewUpload = tkinter.Button(root, text='Start New Upload', command=partial(cb_startNewUpload, root))
    root.button_resumeUpload = tkinter.Button(root, text='Resume Upload', command=partial(cb_resumeUpload, root))

    _row = 0
    root.label_token_id.grid(row=_row, column=0)
    root.entry_token_id.grid(row=_row, column=1)
    root.button_token_id.grid(row=_row, column=2)

    _row = _row + 1
    root.label_pathfilename.grid(row=_row, column=0)
    root.entry_pathfilename.grid(row=_row, column=1)
    root.button_pathfilename.grid(row=_row, column=2)

    _row = _row + 1
    root.label_filename.grid(row=_row, column=0)
    root.entry_filename.grid(row=_row, column=1)

    _row = _row + 1
    root.label_upload_id.grid(row=_row, column=0)
    root.entry_upload_id.grid(row=_row, column=1)

    _row = _row + 1
    root.button_loadConfigFile.grid(row=_row, column=2)

    _row = _row + 1
    root.button_startNewUpload.grid(row=_row, column=0)
    root.button_resumeUpload.grid(row=_row, column=2)

# =================================================================
# main
# =================================================================

def main():
    # Crée l'interface utilisateur
    root = tkinter.Tk()
    createGui(root)
    root.mainloop()

    # readConfigFile('upload_config_2018_09_01_10h05m00s.txt')
    #newResumableUpload(PAHTFILENAME, FILENAME, TOKEN_ID)
    #resumeExistingUpload(PAHTFILENAME, FILENAME, "AEnB2UoFYVglwn1gOGyGZCkMr7Fi9G43PttVy4URdHQxZeBtQaQagdxwHLkI4YTRuHeZdtrix8mM7lTPEVZlNaf9LAw_q7MWuw")
    #resumeFromConfigFile('upload_config_2018_09_01_16h54m44s.ini')

    # _____________________________________ TESTED OK
    #_status, _start, _end = checkUploadComplete(UPLOAD_ID)
    #print (_status)
    #print("Le octets déja transférés sont : " + str(_start) + "-" + str(_end))

    #buff = readIntoFile(PAHTFILENAME, 0, CHUNK_SIZE)
    #buff = readIntoFile("fichier_texte.txt", 0, CHUNK_SIZE)
    #read_size = len(buff)
    #print(buff)
    #print(read_size)

    #size_byte = getFileSize(PAHTFILENAME)
    #print(size_byte)

    #mime = filenameToMimeType(PAHTFILENAME)
    #print(mime)

    #initiateSimpleUpload(PAHTFILENAME, FILENAME, TOKEN_ID)

    #readConfigFile('upload_config_2018_09_01_10h05m00s.txt')

# =================================================================
# Main API 
# =================================================================

# __________________________________________________________________
# Lance un nouveau téléchargement avec possibilité de reprise
def newResumableUpload(pathfilename, filename, token_id):
    _upload_id = initiateNewResumableUpload(pathfilename, filename, token_id)
    saveConfigToFile(pathfilename, filename, _upload_id)
    resumeExistingUpload(pathfilename, filename, _upload_id)

# __________________________________________________________________
# Reprend un téléchargement interrompu
def resumeExistingUpload(pathfilename, filename, upload_id):
    _status, _start, _end = checkUploadComplete(upload_id)
    if ( (_start == 0) and (_end == 0) ):   # cas où aucun octet n'a été transféré
        _start_byte = 0
    else :     
        _start_byte = _end + 1
    while (_status == False) :
        _status, _start, _end = resumeUpload(pathfilename, filename, upload_id, _start_byte, CHUNK_SIZE)
        print (_status)
        _file_size = getFileSize(pathfilename)
        _percent = float(_end)/float(_file_size) * 100
        print("Le octets déja transférés sont : " + str(_start) + "-" + str(_end))
        print("Transfert réalisé à " + str(_percent) + "%")
        if ( (_start == 0) and (_end == 0) ):   # cas où aucun octet n'a été transféré
            _start_byte = 0
        else :     
            _start_byte = _end + 1
    print ("Transfert terminé")

# __________________________________________________________________
# Reprend un téléchargement interrompu à partir des informations contenues 
#  dans un fichier de configuration qui a été enregistré au commencement
#  du téléchargement
def resumeFromConfigFile(cfg_pathfilename):
    _pathfilename, _filename, _upload_id = readConfigFile(cfg_pathfilename)
    resumeExistingUpload(_pathfilename, _filename, _upload_id)

# =================================================================
# API  Helper
# =================================================================
# __________________________________________________________________
# Lance le téléchargement d'un fichier en une fois
# Valable pour les fichiers de taille < 5Mb
def initiateSimpleUpload(pathfilename, filename, token_id):
    """
    """
    file_size = getFileSize(pathfilename)
    # TODO : check if size is more than 5Mb (simple request is limited to 5Mb)
    headers = {
        "Authorization": "Bearer " + token_id,
    }
    para = {
        "name": filename,
    }
    files = {
        'data': ('metadata', json.dumps(para), 'application/json; charset=UTF-8'),
        'file': readIntoFile(pathfilename, 0, file_size)
    }
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
        headers=headers,
        files=files
    )
    log (r.status_code)
    log (r.headers)
    if ( (r.status_code >=200) and (r.status_code <=299) ):
        print ("Transfert du fichier réalisé avec succès")


# __________________________________________________________________
# Initie une communication multi-transfert pour récupérer l'ID du transfert à 
# ré-utiliser pour poursuivre le transfert en cas d'arrêt
def initiateNewResumableUpload(pathfilename, filename, token_id):
    """
    POST https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable HTTP/1.1
    Authorization: Bearer [YOUR_AUTH_TOKEN]
    Content-Length: 38
    Content-Type: application/json; charset=UTF-8
    X-Upload-Content-Type: image/jpeg
    X-Upload-Content-Length: 2000000

    {
    "name": "myObject"
    }    
    """
    file_size = getFileSize(pathfilename)
    headers = {
        "Authorization": "Bearer " + token_id,
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": filenameToMimeType(pathfilename),
        "X-Upload-Content-Length": str(getFileSize(pathfilename))
    }
    para = {
        "name": filename
    }
    r = requests.post(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable",
        headers=headers,
        data=json.dumps(para)
    )
    log (r.status_code)
    log (r.headers)
    if (r.status_code == 200):
        upload_id = r.headers['X-GUploader-UploadID']
        print("Conserver les indications suivantes pour une reprise du transfert en cas d'interruption")
        print ("   X-GUploader-UploadID=" + upload_id)
        print ("   Nom du fichier à télécharger=" + pathfilename)
        print ("   Authentification Token ID=" + token_id)
        return upload_id
    return ""

# ______________________________________________________________________________________
def resumeUpload(pathfilename, filename, upload_id, file_next_byte, chunk_size):
    """
    PUT https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=<upload_id> HTTP/1.1
    Content-Length: 524288
    Content-Type: image/jpeg
    Content-Range: bytes 0-524287/2000000
    """
    file_size = getFileSize(pathfilename)
    data_buff = readIntoFile(pathfilename, file_next_byte, chunk_size)
    data_size = len(data_buff)
    headers = {
        "Content-Length": str(data_size),
        "Content-Type": filenameToMimeType(pathfilename),
        "Content-Range": "bytes " + str(file_next_byte) + "-" + str(file_next_byte + data_size - 1) + "/" + str(file_size)
    }
    print(headers)
    r = requests.put(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=" + upload_id,
        headers=headers,
        data=data_buff
    )
    log("Code de retour : " + str(r.status_code))
    log(r.headers)
    if (r.status_code == 200):
        log ("La dernière session d'upload s'est terminée avec succès.")
        return True, 0, file_size
    elif (r.status_code == 308) : # Le dernier transfert ne s'est pas terminé jusqu'au bout
        _start_byte, _end_byte = rangeToMinMaxValues(r.headers['Range'])
        log("La dernière session d'upload ne s'est pas terminée complètement")
        log ("Les octets reçues lors de la dernière session sont " + str(_start_byte) + "-" + str(_end_byte))
        return False, _start_byte, _end_byte
    return False, 0, 0 # Autre code d'erreur : ne peut pas conclure

# ______________________________________________________________________________________
# Vérifie si un téléchargement est terminé ou non
# Renvoie True si le téléchargement s'est terminé
# Renvoie False si le téléchargement n'est pas terminé
#    Dans ce cas, renvoie également la plage des octets déjà téléchargés pour permettre une reprise

def checkUploadComplete(upload_id):
    headers = {
        "Content-Length": "0",
        "Content-Range": "bytes */*"
    }
    r = requests.put(
        "https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=" + upload_id,
        headers=headers
    )
    log("Code de retour : " + str(r.status_code))
    log(r.headers)
    if (r.status_code == 200):
        log ("La dernière session d'upload s'est terminée avec succès.")
        return True, 0, 0
    elif (r.status_code == 308) : # Le dernier transfert ne s'est pas terminé jusqu'au bout
        range = r.headers.get('Range')
        _start_byte = 0
        _end_byte = 0
        if (range is not None):
            _start_byte, _end_byte = rangeToMinMaxValues(range)
        log("La dernière session d'upload ne s'est pas terminée complètement")
        log ("Les octets reçues lors de la dernière session sont " + str(_start_byte) + "-" + str(_end_byte))
        return False, _start_byte, _end_byte
    return False, 0, 0 # Autre code d'erreur : ne peut pas conclure

# __________________________________________________________________
# Sauvegarde les paramètres d'un transfert dans un fichier text
def saveConfigToFile(pathfilename, filename, upload_id):
    _local_datetime = time.strftime("%Y_%m_%d_%Hh%Mm%Ss", time.localtime())
    cfg_filename = "upload_config_" + _local_datetime + ".ini"
    f = open(cfg_filename, "w")

    Config = configparser.ConfigParser()
    Section = 'DEFAULT'
    Config.set(Section, 'pathfilename', pathfilename)
    Config.set(Section, 'filename', filename)
    Config.set(Section, 'upload_id', upload_id)

    Config.write(f)
    f.close()

# __________________________________________________________________
# Sauvegarde les paramètres d'un transfert dans un fichier text
# Restitue les 3 paramètres du fichiers
def readConfigFile(cfg_pathfilename):
    Config = configparser.ConfigParser()
    Config.read(cfg_pathfilename)

    Section = 'DEFAULT'
    pathfilename = Config[Section]['pathfilename']
    filename = Config[Section]['filename']
    upload_id = Config[Section]['upload_id']
    log ('Lecture du fichier de configuration')
    log ('   - pathfilename = ' + pathfilename)
    log ('   - filename = ' + filename)
    log ('   - upload_id = ' + upload_id)

    return pathfilename, filename, upload_id

# =================================================================
# Authorisation / Token ID
# =================================================================
# __________________________________________________________________
# Crée un nouveau token ID
def createTokenId():
    SCOPES = 'https://www.googleapis.com/auth/drive'

    store = file.Storage('token.json')
    creds = store.get()
    flow = client.flow_from_clientsecrets('credentials.json', SCOPES)
    creds = tools.run_flow(flow, store)
    token_id = creds.access_token
    log ("Récupération d'un nouveau token id : " + str(token_id))
    return token_id

# =================================================================
# Toolbox
# =================================================================
# Affiche des message si autorisé
def log(str):
    if (verbose) :
        print(str)

# Extrait les valeurs min max du range
# Entrée : une chaine au format : "bytes=456-524287"
# Sortie : 2 paramètres de types int représentant les 2 bornes du range
def rangeToMinMaxValues(_str):
    _min = 0
    _max = 0
    _range1 = _str.split("=")
    if (len(_range1) >= 2) : 
        _range2 = _range1[1].split("-")
        if (len(_range2) >= 2) :
            _min = int(_range2[0])
            _max = int(_range2[1])
    return _min, _max


# =================================================================
# Manipulation du fichier 
# =================================================================
# __________________________________________________________________
# Lit une portion du fichier
# start_byte indique la position de départ de la lecture dans le fichier (en octets)
# size indique le nombre d'octets à lire dans le fichier
def readIntoFile(pathfilename, start_byte, size):
    f = open(pathfilename, "rb")
    f.seek(start_byte)
    return f.read(size)

def getFileSize(pathfilename):
    return os.stat(pathfilename).st_size

# __________________________________________________________________
# Creation de la requete
def getRequestUrl(uploadtype="resumable", last_id_transfer=""):
    print("Not yet implemented")

def getRequestHeaders(token_id):
    headers = {"Authorization": "Bearer " + token_id}
    return headers

def getRequestFiles(filename, pathfilename):
    para = {
        "name": filename,
    }
    files = {
        'data': ('metadata', json.dumps(para), 'application/json; charset=UTF-8'),
        'file': open(pathfilename, "rb")
    }
    return files

# __________________________________________________________________
# Renvoie le type MIME d'un fichier
def filenameToMimeType(filename):
    _filename, _extension = os.path.splitext(filename)
    if (_extension == ".zip"): 
        return 'application/zip'
    elif (_extension == ".img"): 
        return 'application/x-raw-disk-image'
    else:
        return 'application/octet-stream'

# ================================================================
if __name__ == '__main__':
    main()

# gdrive_upload_gui
Upload and resume a file to google drive

Ce script permet d'uploader un fichier vers Google Drive en utilisant l'API.
L'intérêt de ce script réside dans le fait qu'il permet de reprendre un upload
 qui a été intérrompu suite à une perte de connexion, ou un plantage du PC durant le transfert, 
 en reprenant le transfert là où il s'était interrompu (sans recommencer le transfert depuis le début).

2 fonctionnalités principales sont proposées : 
  - Initier un nouvel upload
  - Reprendre un upload interrompu

Référence 
  https://developers.google.com/drive/api/v3/resumable-upload

Liste des paquets à installer pour exécuter le script
  pip3 install --upgrade google-api-python-client oauth2client
  pip3 install ConfigParser
  apt-get install python3-tk

Le script s'exécute en python3

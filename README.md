# Mini-Plateforme-IoT-Projet-TP: SensorFlow Hub
Ce projet est un mini-système IoT permettant la **collecte**, le **stockage**, et la **visualisation en temps réel** des données provenant de capteurs.  
Il s’inspire du fonctionnement des plateformes IoT modernes comme **Thinger.io**.
**Objectifs du projet** 
- Développer une plateforme IoT simple et fonctionnelle.
- Connecter un ou plusieurs capteurs via microcontrôleur ESP32
- Transmettre les données via **HTTP**
- Stocker les données dans une base locale ou distante.
- Afficher les mesures sur un **dashboard web interactif**.
- Permettre l’extension future vers un système complet.
**Technologies utilisées**
  **Langages :** Python / JavaScript / HTML / CSS 
- **Backend :** API REST (Flask ou Node.js)  
- **Base de données :** SQLite / JSON / CSV  
- **Frontend :** HTML, CSS, JavaScript (Charts.js)  
- **Communication IoT :** HTTP / MQTT
**Matériel :**
  -ESP32
  - capteur DHT11/ DHT12/
**Fonctionnalités principales**
**Acquisition des données** depuis un capteur IoT
**Envoi des données** au serveur via API REST
**Stockage** des mesures horodatées
**Dashboard web** :  
  - Graphiques temps réel  
  - Historique des données  
  - Rafraîchissement automatique
**Architecture du projet**

/SensorFlow Hub

├── backend/

│ ├── app.py

│ ├── database.db

│ └── routes/

├── frontend/

│ ├── index.html

│ ├── dashboard.js
│ ├── authentification.js

│ └── styles.css

├── device/

│ └── sensor_code.ino

└── README.md

**Résultats obtenus**
Système IoT fonctionnel de bout en bout
API stable pour recevoir et stocker les données
Dashboard intuitif pour surveiller les capteurs
Plateforme extensible type Thinger.io
**Captures d’écran**
 dashboard, code, architecture, etc.
**Réalisé par :**
Roua Jendoubi
TP Internet of Things – 2025
**Licence**
License: MIT © 2025 Roua Jendoubi
    







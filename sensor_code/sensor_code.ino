/*
 * SensorFlow Hub - Code ESP32 avec DHT11/DHT22
 * 
 * Description: 
 * Ce code permet à un ESP32 de lire les données d'un capteur DHT11 ou DHT22
 * et de les envoyer via HTTP à l'API Flask
 * 
 * Matériel requis:
 * - ESP32 DevKit
 * - Capteur DHT11 ou DHT22
 * - Câbles de connexion
 * 
 * Connexions:
 * DHT11/DHT22:
 *   - VCC -> 3.3V ESP32
 *   - GND -> GND ESP32
 *   - DATA -> GPIO 4 (ou autre pin digital)
 *   
 * Auteur: Roua Jendoubi
 * Date: 2025
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ============================================
// CONFIGURATION WIFI
// ============================================
const char* ssid = "VOTRE_SSID";           // Nom de votre réseau WiFi
const char* password = "VOTRE_MOT_DE_PASSE";  // Mot de passe WiFi

// ============================================
// CONFIGURATION SERVEUR API
// ============================================
const char* serverUrl = "http://192.168.1.100:5000/api/data";  // Remplacer par l'IP de votre serveur
const String deviceId = "ESP32_001";  // Identifiant unique de cet ESP32

// ============================================
// CONFIGURATION CAPTEUR DHT
// ============================================
#define DHTPIN 4          // Pin où est connecté le DHT (GPIO 4)
#define DHTTYPE DHT11     // Type de capteur: DHT11 ou DHT22

// Pour DHT22, remplacer par:
// #define DHTTYPE DHT22

DHT dht(DHTPIN, DHTTYPE);

// ============================================
// CONFIGURATION TEMPORISATION
// ============================================
const unsigned long SEND_INTERVAL = 5000;  // Intervalle d'envoi en millisecondes (5 secondes)
unsigned long lastSendTime = 0;

// LED intégrée pour indication visuelle
const int LED_BUILTIN_PIN = 2;

// ============================================
// FONCTION: Configuration initiale
// ============================================
void setup() {
  // Initialisation de la communication série (pour debug)
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n\n");
  Serial.println("================================================");
  Serial.println("    SensorFlow Hub - ESP32 Sensor Node");
  Serial.println("================================================");
  
  // Configuration de la LED
  pinMode(LED_BUILTIN_PIN, OUTPUT);
  digitalWrite(LED_BUILTIN_PIN, LOW);
  
  // Initialisation du capteur DHT
  Serial.println("📡 Initialisation du capteur DHT...");
  dht.begin();
  delay(2000);  // Délai pour stabilisation du capteur
  Serial.println("✅ Capteur DHT initialisé");
  
  // Connexion au WiFi
  connectToWiFi();
  
  Serial.println("\n🚀 Système prêt! Démarrage de l'envoi des données...\n");
}

// ============================================
// FONCTION: Connexion WiFi
// ============================================
void connectToWiFi() {
  Serial.print("📶 Connexion au WiFi: ");
  Serial.println(ssid);
  
  WiFi.begin(ssid, password);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_BUILTIN_PIN, !digitalRead(LED_BUILTIN_PIN));  // Clignotement LED
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\n✅ WiFi connecté!");
    Serial.print("📍 Adresse IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("📶 Puissance du signal: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
    digitalWrite(LED_BUILTIN_PIN, HIGH);  // LED allumée = connecté
  } else {
    Serial.println("\n❌ Échec de connexion WiFi!");
    Serial.println("⚠️  Vérifiez vos identifiants WiFi");
  }
}

// ============================================
// FONCTION: Lecture des données du capteur
// ============================================
bool readSensorData(float &temperature, float &humidity) {
  // Lecture de l'humidité
  humidity = dht.readHumidity();
  
  // Lecture de la température en Celsius
  temperature = dht.readTemperature();
  
  // Vérification si la lecture a échoué
  if (isnan(humidity) || isnan(temperature)) {
    Serial.println("❌ Erreur de lecture du capteur DHT!");
    return false;
  }
  
  // Validation des plages de valeurs
  if (temperature < -40 || temperature > 80) {
    Serial.println("⚠️  Température hors limites!");
    return false;
  }
  
  if (humidity < 0 || humidity > 100) {
    Serial.println("⚠️  Humidité hors limites!");
    return false;
  }
  
  return true;
}

// ============================================
// FONCTION: Envoi des données à l'API
// ============================================
bool sendDataToServer(float temperature, float humidity) {
  // Vérifier la connexion WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("❌ WiFi déconnecté! Tentative de reconnexion...");
    connectToWiFi();
    return false;
  }
  
  HTTPClient http;
  
  // Configuration de la requête HTTP
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/json");
  
  // Création du payload JSON
  StaticJsonDocument<200> jsonDoc;
  jsonDoc["device_id"] = deviceId;
  jsonDoc["temperature"] = temperature;
  jsonDoc["humidity"] = humidity;
  
  String jsonPayload;
  serializeJson(jsonDoc, jsonPayload);
  
  Serial.println("📤 Envoi des données:");
  Serial.println(jsonPayload);
  
  // Envoi de la requête POST
  int httpResponseCode = http.POST(jsonPayload);
  
  bool success = false;
  
  // Traitement de la réponse
  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.print("✅ Réponse serveur (");
    Serial.print(httpResponseCode);
    Serial.print("): ");
    Serial.println(response);
    
    // Clignotement rapide de la LED pour indiquer l'envoi réussi
    for (int i = 0; i < 3; i++) {
      digitalWrite(LED_BUILTIN_PIN, LOW);
      delay(100);
      digitalWrite(LED_BUILTIN_PIN, HIGH);
      delay(100);
    }
    
    success = true;
  } else {
    Serial.print("❌ Erreur HTTP: ");
    Serial.println(httpResponseCode);
    Serial.print("   Erreur: ");
    Serial.println(http.errorToString(httpResponseCode));
  }
  
  http.end();
  return success;
}

// ============================================
// FONCTION: Affichage des données (debug)
// ============================================
void displaySensorData(float temperature, float humidity) {
  Serial.println("┌─────────────────────────────────────┐");
  Serial.print("│ 🌡️  Température: ");
  Serial.print(temperature, 1);
  Serial.println(" °C");
  Serial.print("│ 💧 Humidité:     ");
  Serial.print(humidity, 1);
  Serial.println(" %");
  
  // Calcul de l'index de chaleur (Heat Index)
  float heatIndex = dht.computeHeatIndex(temperature, humidity, false);
  Serial.print("│ 🔥 Index chaleur: ");
  Serial.print(heatIndex, 1);
  Serial.println(" °C");
  Serial.println("└─────────────────────────────────────┘");
}

// ============================================
// BOUCLE PRINCIPALE
// ============================================
void loop() {
  // Vérifier si l'intervalle d'envoi est écoulé
  unsigned long currentTime = millis();
  
  if (currentTime - lastSendTime >= SEND_INTERVAL) {
    lastSendTime = currentTime;
    
    // Variables pour stocker les données
    float temperature, humidity;
    
    // Lecture du capteur
    if (readSensorData(temperature, humidity)) {
      // Affichage des données
      displaySensorData(temperature, humidity);
      
      // Envoi au serveur
      sendDataToServer(temperature, humidity);
      
    } else {
      Serial.println("⏭️  Passage à la prochaine lecture...");
    }
    
    Serial.println();  // Ligne vide pour la lisibilité
  }
  
  // Petit délai pour éviter de surcharger le processeur
  delay(100);
}

// ============================================
// FONCTIONS UTILITAIRES SUPPLÉMENTAIRES
// ============================================

/*
 * Fonction pour vérifier la santé du système
 * Peut être appelée périodiquement pour diagnostiquer les problèmes
 */
void checkSystemHealth() {
  Serial.println("\n🔍 Vérification de la santé du système:");
  
  // Vérifier la connexion WiFi
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("✅ WiFi: Connecté");
    Serial.print("   RSSI: ");
    Serial.print(WiFi.RSSI());
    Serial.println(" dBm");
  } else {
    Serial.println("❌ WiFi: Déconnecté");
  }
  
  // Vérifier la mémoire libre
  Serial.print("💾 Mémoire libre: ");
  Serial.print(ESP.getFreeHeap());
  Serial.println(" bytes");
  
  // Temps de fonctionnement
  Serial.print("⏱️  Uptime: ");
  Serial.print(millis() / 1000);
  Serial.println(" secondes");
  
  Serial.println();
}
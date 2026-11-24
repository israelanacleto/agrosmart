/*
 * AgroSmart - No de sensores de campo (simulacao TinkerCad)
 * Placa: Arduino Uno R3
 *
 * Sensores
 *   A0 - TMP36 ................... temperatura do ar (graus C)
 *   A1 - Sensor de umidade do solo  umidade do solo (%)  [alimentado pelo D7]
 *   A2 - Fotoresistor (LDR) + 10k . luminosidade (%)
 *   A3 - Potenciometro ............ umidade relativa do ar (%) (*)
 *   D2 - Sensor PIR ............... movimento na area (evento)
 *   D3 - Botao (pull-down 10k) .... pluviometro de bascula: chuva (evento)
 *
 * Atuadores
 *   D11 - LED verde ............... status normal
 *   D12 - LED amarelo ............. atencao (solo seco ou ar muito umido)
 *   D13 - LED vermelho ............ critico (solo critico)
 *   D8  - Buzzer (piezo) .......... alarme de intrusao (PIR)
 *   D9  - Rele / motor CC ......... bomba de irrigacao
 *
 * (*) O TinkerCad nao possui sensor DHT11/DHT22; o potenciometro
 *     representa a leitura de umidade relativa do ar.
 *
 * Saida: uma linha CSV por leitura na Serial (9600 baud), lida pelo
 * gateway de campo, que acrescenta data/hora e envia para o Data Lake.
 *
 * Comandos aceitos pela Serial (enviados pelo motor de decisao):
 *   'I' -> liga a bomba de irrigacao
 *   'D' -> desliga a bomba de irrigacao
 */

const char* ID_NO   = "NODE-01";
const char* TALHAO  = "T1";

const int PINO_TEMP  = A0;
const int PINO_SOLO  = A1;
const int PINO_LUZ   = A2;
const int PINO_UR    = A3;
const int PINO_PIR   = 2;
const int PINO_CHUVA = 3;
const int PINO_SOLO_VCC = 7;

const int LED_VERDE    = 11;
const int LED_AMARELO  = 12;
const int LED_VERMELHO = 13;
const int BUZZER       = 8;
const int BOMBA        = 9;

const unsigned long INTERVALO_MS = 2000;   // uma leitura a cada 2 s na simulacao

// Limites da logica local (edge). A decisao completa fica no motor central.
const int SOLO_SECO     = 30;   // %
const int SOLO_CRITICO  = 15;   // % - aciona a bomba como protecao local
const int UR_ALTA       = 85;   // %

bool bombaLigada = false;
bool bombaPorComando = false;
bool movimentoNoCiclo = false;
bool chuvaNoCiclo = false;
unsigned long ultimoEnvio = 0;

float lerTemperatura() {
  int bruto = analogRead(PINO_TEMP);
  float tensao = bruto * (5.0 / 1023.0);
  return (tensao - 0.5) * 100.0;          // TMP36: 10 mV/C com offset de 500 mV
}

int lerUmidadeSolo() {
  digitalWrite(PINO_SOLO_VCC, HIGH);      // energiza so na leitura (reduz corrosao)
  delay(10);
  int bruto = analogRead(PINO_SOLO);
  digitalWrite(PINO_SOLO_VCC, LOW);
  return constrain(map(bruto, 0, 876, 0, 100), 0, 100);  // 876 = maximo do sensor no TinkerCad
}

int lerLuminosidade() {
  int bruto = analogRead(PINO_LUZ);
  return constrain(map(bruto, 0, 1023, 0, 100), 0, 100);
}

int lerUmidadeAr() {
  int bruto = analogRead(PINO_UR);
  return constrain(map(bruto, 0, 1023, 0, 100), 0, 100);
}

void acionarBomba(bool ligar) {
  bombaLigada = ligar;
  digitalWrite(BOMBA, ligar ? HIGH : LOW);
}

void lerComandos() {
  while (Serial.available() > 0) {
    char c = Serial.read();
    if (c == 'I') { bombaPorComando = true;  acionarBomba(true); }
    if (c == 'D') { bombaPorComando = false; acionarBomba(false); }
  }
}

void atualizarSinalizacao(int solo, int ur, bool movimento) {
  bool critico = solo < SOLO_CRITICO;
  bool atencao = !critico && (solo < SOLO_SECO || ur >= UR_ALTA);

  digitalWrite(LED_VERMELHO, critico ? HIGH : LOW);
  digitalWrite(LED_AMARELO,  atencao ? HIGH : LOW);
  digitalWrite(LED_VERDE,    (!critico && !atencao) ? HIGH : LOW);

  if (movimento) tone(BUZZER, 1000, 300); else noTone(BUZZER);

  // Protecao local: solo critico liga a bomba mesmo sem comando central
  if (critico) acionarBomba(true);
  else if (!bombaPorComando) acionarBomba(false);
}

void setup() {
  Serial.begin(9600);
  pinMode(PINO_PIR, INPUT);
  pinMode(PINO_CHUVA, INPUT);
  pinMode(PINO_SOLO_VCC, OUTPUT);
  pinMode(LED_VERDE, OUTPUT);
  pinMode(LED_AMARELO, OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(BUZZER, OUTPUT);
  pinMode(BOMBA, OUTPUT);

  Serial.println("no_sensor,talhao,millis,temperatura_c,umidade_ar_pct,umidade_solo_pct,luminosidade_pct,movimento,chuva,bomba");
}

void loop() {
  lerComandos();

  // Eventos sao acumulados entre um envio e outro para nao se perderem
  if (digitalRead(PINO_PIR) == HIGH)   movimentoNoCiclo = true;
  if (digitalRead(PINO_CHUVA) == HIGH) chuvaNoCiclo = true;

  if (millis() - ultimoEnvio < INTERVALO_MS) return;
  ultimoEnvio = millis();

  float temperatura = lerTemperatura();
  int umidadeAr  = lerUmidadeAr();
  int umidadeSolo = lerUmidadeSolo();
  int luz = lerLuminosidade();

  atualizarSinalizacao(umidadeSolo, umidadeAr, movimentoNoCiclo);

  Serial.print(ID_NO);              Serial.print(',');
  Serial.print(TALHAO);             Serial.print(',');
  Serial.print(millis());           Serial.print(',');
  Serial.print(temperatura, 1);     Serial.print(',');
  Serial.print(umidadeAr);          Serial.print(',');
  Serial.print(umidadeSolo);        Serial.print(',');
  Serial.print(luz);                Serial.print(',');
  Serial.print(movimentoNoCiclo ? 1 : 0); Serial.print(',');
  Serial.print(chuvaNoCiclo ? 1 : 0);     Serial.print(',');
  Serial.println(bombaLigada ? 1 : 0);

  movimentoNoCiclo = false;
  chuvaNoCiclo = false;
}

#include <math.h>
 
// microstepping pins
#define M0 2              
#define M1 3
#define M2 6

// other pins for stepping the motor
#define STEP_PIN 7
#define DIR_PIN 8

// pins for buttons used to manually control the motor
#define FLUSH 9
#define REV 10

// parameters for serial communication
#define BAUD_RATE 230400  // the rate at which data is read
// The buffer allows us to store bytes as they are read from the python program (64 bytes in size)
const byte buffSize = 64;
char inputBuffer[buffSize];
// We create inputs to this program by <...> where <> represent the startread and endread markers
const char startMarker = '<';
const char endMarker = '>';
byte bytesRecvd = 0;
bool readInProgress = false;
bool newDataFromPC = false;
char mode[buffSize] = {0};
char setting[buffSize] = {0};
float value = 0.0;
char dir[buffSize] = {0};

// order of microstep levels: {"Full", "Half", "1/4", "1/8", "1/16", "1/32"};
const int microsteps_per_rev[6] = {200, 400, 800, 1600, 3200, 6400};
const bool microstep_settings[6][3] = {
  {false, false, false},
  {true, false, false},
  {false, true, false},
  {true, true, false},
  {false, false, true},
  {true, false, true}
};
int curr_microstep_lvl;

//parameters for stepping the motor and keeping track of position
int direction = 1;               // direction to move the piston (+1 for forward -1 for backward)
unsigned long steps_to_go = 0;   // number of microsteps left to complete the current move
unsigned long step_interval;     // inter-step interval in microseconds (computed when calling setSpeed(speed))
unsigned long speed;             // motor speed in microsteps per second
unsigned long last_step;         // time in microseconds since boot of the last step of the motor
const float lead = 0.2;          // lead of the lead screw in cm
float position = 0;              // position of the piston in cm
float cmPerStep;                 // cm traveled by the piston per microstep (computed when setting the microstep level)
float distance;                  // requested distance to move the piston
int running = 0;                 // whether or not the pump is currently running (1 if running 0 if not)
bool running_manual = false;     // whether or not the pump is being controlled manually
float pulse_width = 5;           // width of pulses used to step the motor in microseconds

unsigned long last_log;          // time since boot in milliseconds of the last log
int log_interval = 100;          // time interval in milliseconds between logs
int moveCompleted = 1;           // flag to be raised when a move has been completed and cleared (set to 0) before the start of a move

void setup() {


  Serial.begin(BAUD_RATE);

  //step and dir pins
  pinMode(STEP_PIN, OUTPUT);
  pinMode(DIR_PIN, OUTPUT);
  digitalWrite(DIR_PIN, LOW);
  digitalWrite(STEP_PIN, LOW);


  // Set microstep pins
  pinMode(M0, OUTPUT);
  pinMode(M1, OUTPUT);
  pinMode(M2, OUTPUT);

  set_microstep_lvl(0);
  setSpeed(1000);

  // Set initial speed and acceleration
  pinMode(FLUSH, INPUT);
  pinMode(REV, INPUT);

  last_log = millis();
  last_step = micros();
}

void loop() {

  bool to_flush = digitalRead(FLUSH);
  bool to_rev = digitalRead(REV);

  if (running!=1 && (to_flush || to_rev)){
    if (to_rev) {direction = -1;}
    else {direction = 1;}
    setTarget(10000);
    running_manual = true;
  } else if (running_manual && !(to_flush || to_rev)){
    stop();
  }

  step();
  getDataFromPC();

  if ((millis() - last_log) >= log_interval){
    Serial.print(position);
    Serial.print(",");
    Serial.print(running);
    Serial.print(",");
    Serial.print(direction);
    Serial.print(",");
    Serial.print(moveCompleted);
    Serial.print(",");
    Serial.print(curr_microstep_lvl);
    Serial.print(",");
    Serial.println(speed);
    last_log = millis();
  }
}

void step(){

  // check if the motor is due for a microstep and if so step
  // similar to the run method of AccelStepper
  // thist should be called as frequently as possible

  if ((running==1) && (steps_to_go>0)){
    if((micros() - last_step) >= step_interval){
      digitalWrite(DIR_PIN, direction == 1);
      digitalWrite(STEP_PIN, HIGH);
      last_step = micros();
      delayMicroseconds(pulse_width);
      digitalWrite(STEP_PIN, LOW);
      position -= direction * cmPerStep;
      steps_to_go -= 1;
      if (steps_to_go==0){
        running=0;
        moveCompleted = 1;
      }
    }
  }
}

void stop(){
  // stop any currently running pump tasks
  steps_to_go = 0;
  running = 0;
  running_manual = false;
}

void setTarget(unsigned long target){
  // set the target number of microsteps for the motor
  steps_to_go = target;
  if (target > 0){running = 1;}
  last_step = micros();
}

void setSpeed(float _speed){
  // set the speed that the motor will step
  float _step_interval = 1000000/_speed;
  if (_step_interval > (100 * pulse_width)){
    step_interval = _step_interval;
    speed = _speed;
  }
}

void set_microstep_lvl(int microstep_lvl){
   if ((microstep_lvl < sizeof(microsteps_per_rev)) && (microstep_lvl>=0)) {
    if (running==1){
      // if the motor is currently moving update the number of microsteps to go
      // so the motor reaches the same target
      float conversion = float(microsteps_per_rev[microstep_lvl])/float(microsteps_per_rev[curr_microstep_lvl]);
      steps_to_go = round(steps_to_go*conversion);
    }
    curr_microstep_lvl = microstep_lvl;
   }
   cmPerStep = get_cmPerStep();
   update_microstep_pins();
}

void update_microstep_pins(){
  digitalWrite(M0, microstep_settings[curr_microstep_lvl][0]);
  digitalWrite(M1, microstep_settings[curr_microstep_lvl][1]);
  digitalWrite(M2, microstep_settings[curr_microstep_lvl][2]);
}

float get_cmPerStep(){
  return lead/microsteps_per_rev[curr_microstep_lvl];
}

// the following is adapted from the original poseidon code
void getDataFromPC() {

  // If there is data from the serial port
  if (Serial.available() > 0) {
    // read a single character
    char x = Serial.read();

    // the order of these IF clauses is significant
    if (x == endMarker) {
      readInProgress = false;
      newDataFromPC = true;
      // clear the buffer
      inputBuffer[bytesRecvd] = 0;
      // and parse the data
      return parseData();
    }

    if (readInProgress) {
      // add the character to the buffer
      inputBuffer[bytesRecvd] = x;
      bytesRecvd ++;
      if (bytesRecvd == buffSize) {
        bytesRecvd = buffSize - 1;
      }
    }

    if (x == startMarker) {
      bytesRecvd = 0;
      readInProgress = true;
    }
  }
}

//=============

/*
  # <Mode, Setting, Value>
  # Mode can be SETTING, RUN, STOP, CALIBRATE, CLEAR 
  # Setting can be SPEED, MICROSTEP
*/

// Here is where we take the string <...> that we have read from the serial port and parse it
void parseData() {

  // split the data into its parts
  // strtok scans the string inputBuffer until it reaches a "," or a ">"
  // Then we declare the variable associated with that part of the inputBuffer
  // each strtok contiues where the previous call left off

  char * strtokIndx; // this is used by strtok() as an index

  strtokIndx = strtok(inputBuffer, ",");     // get the first part - the mode string
  strcpy(mode, strtokIndx);                  // copy it to messageFromPC

  strtokIndx = strtok(NULL, ",");            // get the second part - the setting string
  strcpy(setting, strtokIndx);               // copy it to messageFromPC

  strtokIndx = strtok(NULL, ",");            // get the fourth part - the value float
  value = atof(strtokIndx);                  // convert to float and copy to value

  strtokIndx = strtok(NULL, ",");            // get the fifth part - the direction character
  strcpy(dir, strtokIndx);                   // copy the character to dire

  strtokIndx = strtok(NULL, ",");            // get the fourth part - the value float
  distance = atof(strtokIndx);                // convert to float and copy to value

  newDataFromPC = true;
  return executeThisFunction();
  }

// =============================
// So we do a string comparison using strcmp(str1, str2) as a condition to determine what to do next
// Here we can add new functions if we like, for example if we wanted to add a "TEST" to the mode
// input we would add a condition if (strcmp(mode, "TEST") == 0 {...}
void executeThisFunction() {

  if (strcmp(mode, "STOP") == 0) {stop();}

  else if (strcmp(mode, "SETTING") == 0) {udpateSettings();}

  else if (strcmp(mode, "RUN") == 0) {
    // Check if any stepper is currently running and do not allow execution if that is the case
    if (running_manual){stop();}
    if (running == 0) {
      direction = 1;
      if (strcmp(dir, "B") == 0) {
        direction = -1;
      }
      setTarget(int(round(distance/cmPerStep)));
    }
  }
  else if (strcmp(mode, "CALIBRATE") == 0) {
    position = 0;
  }
  else if (strcmp(mode, "CLEAR") == 0){
    moveCompleted = 0;
  }
}

void udpateSettings() {
  if (strcmp(setting, "SPEED") == 0) {
    setSpeed(value);
  }
  else if (strcmp(setting, "MICROSTEP") == 0) {
    set_microstep_lvl(value);
  }
}
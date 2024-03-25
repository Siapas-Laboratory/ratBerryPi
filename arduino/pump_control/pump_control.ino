#include <AccelStepper.h>
#include <math.h>

// Define stepper motor connections and steps per revolution
#define BAUD_RATE 230400  // the rate at which data is read
#define M0 2
#define M1 3
#define M2 4
#define STEP_PIN 5
#define DIR_PIN 6
#define FLUSH 8
#define REV 9

// Create stepper motor object
AccelStepper stepper(AccelStepper::DRIVER, STEP_PIN, DIR_PIN);

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
const float pitch = 0.08;
int curr_microstep_lvl;

int direction = 1;
float position = 0; // position of the piston in cm
float cmPerStep;
float distance;
bool running_manual = false;

void setup() {

  Serial.begin(BAUD_RATE);

  // Set microstep pins
  pinMode(M0, OUTPUT);
  pinMode(M1, OUTPUT);
  pinMode(M2, OUTPUT);

  set_microstep_lvl("Full");

  // Set initial speed and acceleration
  stepper.setMaxSpeed(1000); // Adjust the speed according to your requirement
  stepper.setAcceleration(5000.0); // Adjust the acceleration according to your requirement

  pinMode(FLUSH, INPUT);
  pinMode(REV, INPUT);
}

void loop() {
  bool to_flush = digitalRead(FLUSH);
  bool to_rev = digitalRead(REV);
  if (!stepper.isRunning() && (to_flush || to_rev)){
    if (to_rev) {direction = -1;}
    else {direction = 1;}
    stepper.move(direction * 10000);
    running_manual = true;
  }
  else if (running_manual && !(to_flush || to_rev)){
    stepper.stop();
    running_manual = false;
  }
  if (stepper.isRunning()){
    stepper.run();
    position += direction * cmPerStep;
  }
  getDataFromPC();
  Serial.println(position);
}

void set_microstep_lvl(int microstep_lvl){
   if ((microstep_lvl < sizeof(microsteps_per_rev)) && (microstep_lvl>=0)) {
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
  return pitch/microsteps_per_rev[curr_microstep_lvl];
}

void calibrate(){
  position = 0;
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
  # Mode can be SETTING, RUN, STOP
  # Setting can be SPEED, ACCEL, DELTA, ONE, FEW, ALL, ZERO
  # Pump number can be 1 or 2 or 3 or 12 or 13 or 23. (## indicates two pumps to run)
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

  if (strcmp(mode, "STOP") == 0) {
    stepper.stop();
    running_manual = false;
  }

  else if (strcmp(mode, "SETTING") == 0) {
    udpateSettings();
  }

  else if (strcmp(mode, "RUN") == 0) {
    // Check if any stepper is currently running and do not allow execution if that is the case
    if (running_manual){
      stepper.stop();
      running_manual = false;
    }
    if (!stepper.isRunning()) {
      direction = 1;
      if (strcmp(dir, "B") == 0) {
        direction = -1;
      }
      stepper.move(direction * int(round(distance/cmPerStep)));
    }
  }
  else if (strcmp(mode, "CALIBRATE") == 0) {
    calibrate();
  }

}

void udpateSettings() {
  if (strcmp(setting, "SPEED") == 0) {
    stepper.setMaxSpeed(value);
  }
  else if (strcmp(setting, "ACCEL") == 0) {
    stepper.setAcceleration(value);
  }
  else if (strcmp(setting, "MICROSTEP") == 0) {
    set_microstep_lvl(value);
  }
}
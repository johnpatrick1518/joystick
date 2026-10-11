#include "../firmware/kenny_motor_test/test_commands.h"
#include <cassert>
#include <iostream>

int main() {
  int directions[4];
  const char* names[] = {"LF", "RF", "LR", "RR"};
  for (int i = 0; i < 4; ++i) {
    for (char sign : {'+', '-'}) {
      char command[] = {names[i][0], names[i][1], sign, 0};
      assert(testDirections(command, directions));
      for (int j = 0; j < 4; ++j) assert(directions[j] == (i == j ? (sign == '+' ? 1 : -1) : 0));
    }
  }
  assert(testDirections("ALL+", directions));
  for (int value : directions) assert(value == 1);
  assert(testDirections("ALL-", directions));
  for (int value : directions) assert(value == -1);
  assert(testDirections("LEFT", directions));
  assert(directions[0] == -1 && directions[2] == -1 && directions[1] == 1 && directions[3] == 1);
  assert(testDirections("RIGHT", directions));
  assert(directions[0] == 1 && directions[2] == 1 && directions[1] == -1 && directions[3] == -1);
  assert(testDirections("STOP", directions));
  for (int value : directions) assert(value == 0);
  for (const char* invalid : {"", "ALL", "ALL++", "LF", "LF++", "XX+", "LEFT!"}) {
    assert(!testDirections(invalid, directions));
    for (int value : directions) assert(value == 0);
  }
  std::cout << "Motor commands passed: individual, all forward/reverse, opposite-side turns, stop and invalid input\n";
}

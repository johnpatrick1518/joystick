#pragma once
#include <cstring>

// Logical wheel order: LF, RF, LR, RR. Zero leaves a channel disabled.
inline bool testDirections(const char* command, int (&out)[4]) {
  for (int& value : out) value = 0;
  if (std::strcmp(command, "STOP") == 0) return true;
  if (std::strcmp(command, "ALL+") == 0 || std::strcmp(command, "ALL-") == 0) {
    for (int& value : out) value = command[3] == '+' ? 1 : -1;
    return true;
  }
  if (std::strcmp(command, "LEFT") == 0 || std::strcmp(command, "RIGHT") == 0) {
    int left = std::strcmp(command, "LEFT") == 0 ? -1 : 1;
    out[0] = out[2] = left;
    out[1] = out[3] = -left;
    return true;
  }
  if (std::strlen(command) != 3 || (command[2] != '+' && command[2] != '-')) return false;
  const char* names[] = {"LF", "RF", "LR", "RR"};
  for (unsigned i = 0; i < 4; ++i) {
    if (command[0] == names[i][0] && command[1] == names[i][1]) {
      out[i] = command[2] == '+' ? 1 : -1;
      return true;
    }
  }
  return false;
}

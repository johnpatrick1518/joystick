#pragma once
#include <cstring>
#include "control.h"

namespace mobile {
enum class UsbKind { Invalid, Hello, Status, Arm, Drive, Stop };
// Caller provides a bounded, mutable ASCII line. Reject extra/missing fields.
inline UsbKind parseUsb(char* line, Command& command) {
  char* fields[7] = {};
  unsigned count = 0;
  char* context = nullptr;
  for (char* field = strtok_r(line, " \t", &context); field;
       field = strtok_r(nullptr, " \t", &context)) {
    if (count == 7) return UsbKind::Invalid;
    fields[count++] = field;
  }
  if (!count) return UsbKind::Invalid;
  if (count == 1) {
    if (!strcmp(fields[0], "HELLO")) return UsbKind::Hello;
    if (!strcmp(fields[0], "STATUS")) return UsbKind::Status;
    if (!strcmp(fields[0], "ARM")) { command.kind = Kind::Arm; return UsbKind::Arm; }
    if (!strcmp(fields[0], "STOP")) { command.kind = Kind::Stop; return UsbKind::Stop; }
  }
  if (count == 5 && !strcmp(fields[0], "V") &&
      readUnsigned(fields[1], command.lease) && command.lease &&
      readUnsigned(fields[2], command.sequence) &&
      readFloat(fields[3], command.linear) && readFloat(fields[4], command.angular) &&
      std::fabs(command.linear) <= MAX_LINEAR && std::fabs(command.angular) <= MAX_ANGULAR) {
    command.kind = Kind::Drive;
    return UsbKind::Drive;
  }
  return UsbKind::Invalid;
}
}  // namespace mobile

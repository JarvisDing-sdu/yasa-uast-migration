#ifndef MIXED_SHARED_H
#define MIXED_SHARED_H
#include <stdlib.h>
static inline const char *header_command(void) {
#if defined(__cplusplus) && HEADER_UNTRUSTED
  return getenv("YASA_MIXED_COMMAND");
#else
  return "printf header safe";
#endif
}
#endif

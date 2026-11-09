#ifndef MIXED_SLOT_H
#define MIXED_SLOT_H
inline const char *slot(const char *value, int write) {
  static const char *saved = "printf slot safe";
  if (write) saved = value;
  return saved;
}
#endif

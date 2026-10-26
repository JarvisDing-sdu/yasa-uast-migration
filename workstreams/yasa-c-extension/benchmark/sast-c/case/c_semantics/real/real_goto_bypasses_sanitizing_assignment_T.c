/*
 * evaluation information start
 * real case = true
 * evaluation item = goto
 * scene introduction = 真实 API
 * bind_url = c_semantics/real/real_goto_bypasses_sanitizing_assignment_T
 * evaluation information end
 */
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

void real_goto_bypasses_sanitizing_assignment_T(void) {
    char *p = getenv("YASA_QUALITY");
    goto done;
unused:
    p = "safe";
done:
    system(p);
}

#ifndef HP2_PHYSICS_H
#define HP2_PHYSICS_H

#include "dpsx.h"
#include <stdbool.h>

typedef struct {
    float x, y, z;
    float vy;
    float yaw, pitch;
    bool on_ground;
    bool noclip;
} Player;

void physics_find_spawn(const DpsxLevel *lvl, Player *p);
bool physics_ground_y(const DpsxLevel *lvl, float x, float z, float cur_y, float *out_y);
void physics_step(const DpsxLevel *lvl, Player *p, float move_fwd, float move_right, bool jump, float dt);

#endif

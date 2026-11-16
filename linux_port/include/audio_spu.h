#ifndef HP2_AUDIO_SPU_H
#define HP2_AUDIO_SPU_H

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t dev_id;
    bool ready;
} AudioEngine;

int audio_init(AudioEngine *ae);
void audio_shutdown(AudioEngine *ae);
/* build_assets/audio/WAD/<wad>/<idx>.wav veya doğrudan WAV dosyası çalar */
int audio_play_wav(AudioEngine *ae, const char *wav_path);

#endif

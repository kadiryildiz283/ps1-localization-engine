#include "audio_spu.h"
#include <SDL2/SDL.h>
#include <stdio.h>

int audio_init(AudioEngine *ae) {
    ae->dev_id = 0;
    ae->ready = false;
    SDL_AudioSpec want = {0};
    want.freq = 22050;
    want.format = AUDIO_S16LSB;
    want.channels = 1;
    want.samples = 1024;
    SDL_AudioSpec have = {0};
    ae->dev_id = SDL_OpenAudioDevice(NULL, 0, &want, &have, SDL_AUDIO_ALLOW_FREQUENCY_CHANGE | SDL_AUDIO_ALLOW_CHANNELS_CHANGE);
    if (ae->dev_id == 0) {
        fprintf(stderr, "SDL_OpenAudioDevice uyarısı: %s\n", SDL_GetError());
        return -1;
    }
    SDL_PauseAudioDevice((SDL_AudioDeviceID)ae->dev_id, 0);
    ae->ready = true;
    return 0;
}

void audio_shutdown(AudioEngine *ae) {
    if (ae->ready && ae->dev_id) {
        SDL_CloseAudioDevice((SDL_AudioDeviceID)ae->dev_id);
    }
    ae->dev_id = 0;
    ae->ready = false;
}

int audio_play_wav(AudioEngine *ae, const char *wav_path) {
    if (!ae->ready) return -1;
    SDL_AudioSpec spec;
    uint8_t *buf = NULL;
    uint32_t len = 0;
    if (!SDL_LoadWAV(wav_path, &spec, &buf, &len)) return -1;

    /* Cihaz formatına dönüştür (22050 Hz, S16LSB, mono) */
    SDL_AudioSpec dev_spec = {0};
    dev_spec.freq = 22050;
    dev_spec.format = AUDIO_S16LSB;
    dev_spec.channels = 1;
    SDL_AudioCVT cvt;
    if (SDL_BuildAudioCVT(&cvt, spec.format, spec.channels, spec.freq,
                          dev_spec.format, dev_spec.channels, dev_spec.freq) >= 0) {
        if (cvt.needed) {
            cvt.len = (int)len;
            cvt.buf = SDL_malloc((size_t)(len * cvt.len_mult));
            memcpy(cvt.buf, buf, len);
            SDL_ConvertAudio(&cvt);
            SDL_ClearQueuedAudio((SDL_AudioDeviceID)ae->dev_id);
            SDL_QueueAudio((SDL_AudioDeviceID)ae->dev_id, cvt.buf, (uint32_t)cvt.len_cvt);
            SDL_free(cvt.buf);
        } else {
            SDL_ClearQueuedAudio((SDL_AudioDeviceID)ae->dev_id);
            SDL_QueueAudio((SDL_AudioDeviceID)ae->dev_id, buf, len);
        }
    }
    SDL_FreeWAV(buf);
    return 0;
}

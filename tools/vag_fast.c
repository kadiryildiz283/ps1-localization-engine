/* High-performance Sony PS1 SPU ADPCM encoder */
#include <stdint.h>
#include <stdlib.h>
#include <math.h>
#include <string.h>

static const double IK0[5] = {0.0, 0.9375, 1.796875, 1.53125, 1.90625};
static const double IK1[5] = {0.0, 0.0, -0.8125, -0.859375, -0.9375};

int encode_vag_fast(const int16_t* pcm, int num_samples, uint8_t* out_vag, int loop) {
    int pad_needed = (28 - (num_samples % 28)) % 28;
    int total_samples = num_samples + pad_needed;
    int num_blocks = total_samples / 28;

    int16_t* padded = (int16_t*)malloc(total_samples * sizeof(int16_t));
    if (!padded) return 0;
    memcpy(padded, pcm, num_samples * sizeof(int16_t));
    if (pad_needed > 0) {
        memset(padded + num_samples, 0, pad_needed * sizeof(int16_t));
    }

    double hist1 = 0.0, hist2 = 0.0;
    int out_pos = 0;

    for (int b = 0; b < num_blocks; b++) {
        const int16_t* block = padded + b * 28;
        int is_last = (b == num_blocks - 1);
        uint8_t flag = (is_last && !loop) ? 0x01 : 0x00;

        double best_err = 1e30;
        int best_filter = 0;
        int best_shift = 0;
        int best_nibbles[28];
        double best_h1 = hist1;
        double best_h2 = hist2;

        for (int f_idx = 0; f_idx < 5; f_idx++) {
            double f0 = IK0[f_idx];
            double f1 = IK1[f_idx];

            double temp_h1 = hist1;
            double temp_h2 = hist2;
            double deltas[28];
            double max_delta = 0.0;

            for (int s = 0; s < 28; s++) {
                double pred = f0 * temp_h1 + f1 * temp_h2;
                double d = (double)block[s] - pred;
                deltas[s] = d;
                temp_h2 = temp_h1;
                temp_h1 = (double)block[s];
                double ad = fabs(d);
                if (ad > max_delta) max_delta = ad;
            }

            int min_shift = 0;
            while (min_shift < 12 && (max_delta / (double)(1 << (12 - min_shift))) > 7.0) {
                min_shift++;
            }

            int max_shift = min_shift + 3;
            if (max_shift > 13) max_shift = 13;

            for (int shift = min_shift; shift < max_shift; shift++) {
                double scale = (double)(1 << (12 - shift));
                double curr_h1 = hist1;
                double curr_h2 = hist2;
                double curr_err = 0.0;
                int nibbles[28];

                for (int s = 0; s < 28; s++) {
                    double pred_val = f0 * curr_h1 + f1 * curr_h2;
                    double diff = (double)block[s] - pred_val;
                    int nib = (int)round(diff / scale);
                    if (nib > 7) nib = 7;
                    if (nib < -8) nib = -8;
                    double recon = (double)((nib << 12) >> shift);
                    double sample = recon + pred_val;
                    curr_h2 = curr_h1;
                    curr_h1 = sample;
                    curr_err += ((double)block[s] - sample) * ((double)block[s] - sample);
                    nibbles[s] = nib & 0x0F;
                }

                if (curr_err < best_err) {
                    best_err = curr_err;
                    best_filter = f_idx;
                    best_shift = shift;
                    best_h1 = curr_h1;
                    best_h2 = curr_h2;
                    for (int s = 0; s < 28; s++) {
                        best_nibbles[s] = nibbles[s];
                    }
                }
            }
        }

        uint8_t byte0 = (uint8_t)((best_filter << 4) | (best_shift & 0x0F));
        out_vag[out_pos++] = byte0;
        out_vag[out_pos++] = flag;
        for (int n = 0; n < 28; n += 2) {
            uint8_t low = (uint8_t)best_nibbles[n];
            uint8_t high = (uint8_t)best_nibbles[n + 1];
            out_vag[out_pos++] = (uint8_t)(low | (high << 4));
        }

        hist1 = best_h1;
        hist2 = best_h2;
    }

    free(padded);
    return out_pos;
}

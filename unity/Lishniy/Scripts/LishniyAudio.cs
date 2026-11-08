using UnityEngine;

namespace Lishniy
{
    /// <summary>
    /// Звуки, сгенерированные кодом. Если в инспекторе подставлены свои клипы,
    /// эти не используются.
    /// </summary>
    public static class LishniyAudio
    {
        const int Rate = 44100;

        /// <summary>Глухой шаг по полу.</summary>
        public static AudioClip Footstep()
        {
            int n = (int)(Rate * 0.28f);
            var data = new float[n];
            var rng = new System.Random(1);
            float lp = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float noise = (float)(rng.NextDouble() * 2 - 1);
                lp += 0.08f * (noise - lp);
                float thump = Mathf.Sin(2 * Mathf.PI * 62f * t) * Mathf.Exp(-t * 28f);
                data[i] = (lp * 2.2f * Mathf.Exp(-t * 22f) + thump * 0.8f) * 0.9f;
            }
            return Make("Lishniy_Step", data);
        }

        /// <summary>Низкий гул с биением — его скорее чувствуешь, чем слышишь.</summary>
        public static AudioClip Drone()
        {
            const float len = 6f; // частоты подобраны так, чтобы петля была бесшовной
            int n = (int)(Rate * len);
            var data = new float[n];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float s = Mathf.Sin(2 * Mathf.PI * 41f * t) * 0.5f
                        + Mathf.Sin(2 * Mathf.PI * 43.5f * t) * 0.5f
                        + Mathf.Sin(2 * Mathf.PI * 82.5f * t) * 0.15f
                        + Mathf.Sin(2 * Mathf.PI * 311.5f * t) * 0.02f * (0.5f + 0.5f * Mathf.Sin(2 * Mathf.PI * t / 3f));
                data[i] = s * 0.6f;
            }
            return Make("Lishniy_Drone", data);
        }

        /// <summary>Медленное дыхание прямо за спиной.</summary>
        public static AudioClip Breath()
        {
            const float len = 3.2f;
            int n = (int)(Rate * len);
            var data = new float[n];
            var rng = new System.Random(2);
            float lpA = 0f, lpB = 0f;
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float noise = (float)(rng.NextDouble() * 2 - 1);
                lpA += 0.25f * (noise - lpA);
                lpB += 0.03f * (noise - lpB);
                float band = lpA - lpB; // шипение без верхов и низов

                float env = 0f;
                if (t < 1.3f) env = Mathf.Sin(Mathf.PI * t / 1.3f) * 0.6f;              // вдох
                else if (t > 1.5f && t < 2.9f) env = Mathf.Sin(Mathf.PI * (t - 1.5f) / 1.4f); // выдох
                data[i] = band * env * 1.6f;
            }
            return Make("Lishniy_Breath", data);
        }

        /// <summary>Резкий диссонансный визг для поимки.</summary>
        public static AudioClip Sting()
        {
            const float len = 1.6f;
            int n = (int)(Rate * len);
            var data = new float[n];
            var rng = new System.Random(3);
            float[] freqs = { 1100f, 1167f, 1241f, 553f, 587f };
            float[] phase = new float[freqs.Length];
            for (int i = 0; i < n; i++)
            {
                float t = (float)i / Rate;
                float slide = 1f - 0.35f * (t / len);
                float s = 0f;
                for (int k = 0; k < freqs.Length; k++)
                {
                    phase[k] += 2 * Mathf.PI * freqs[k] * slide / Rate;
                    s += Mathf.Sin(phase[k] + Mathf.Sin(phase[k] * 0.5f) * 1.5f);
                }
                float noise = (float)(rng.NextDouble() * 2 - 1);
                float env = Mathf.Min(1f, t / 0.015f) * Mathf.Exp(-t * 1.8f);
                data[i] = Mathf.Clamp((s / freqs.Length * 0.9f + noise * 0.35f) * env * 1.4f, -1f, 1f);
            }
            return Make("Lishniy_Sting", data);
        }

        static AudioClip Make(string name, float[] data)
        {
            AudioClip clip = AudioClip.Create(name, data.Length, 1, Rate, false);
            clip.SetData(data, 0);
            return clip;
        }
    }
}

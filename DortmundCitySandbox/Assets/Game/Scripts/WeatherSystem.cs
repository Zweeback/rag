using System.Collections;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Cycles through weather presets blending particle systems and lighting.
    /// </summary>
    public class WeatherSystem : MonoBehaviour
    {
        [System.Serializable]
        public class WeatherPreset
        {
            public string name;
            public ParticleSystem particlePrefab;
            public Color fogColor = Color.gray;
            public float fogDensity = 0.01f;
        }

        [SerializeField] private WeatherPreset[] presets;
        [SerializeField] private float transitionSeconds = 30f;
        [SerializeField] private int startIndex = 0;

        private ParticleSystem activeParticleSystem;
        private int currentIndex;

        private void Start()
        {
            ApplyPreset(startIndex);
            StartCoroutine(CycleWeather());
        }

        private IEnumerator CycleWeather()
        {
            while (true)
            {
                yield return new WaitForSeconds(transitionSeconds);
                currentIndex = (currentIndex + 1) % Mathf.Max(1, presets.Length);
                ApplyPreset(currentIndex);
            }
        }

        private void ApplyPreset(int index)
        {
            if (presets == null || presets.Length == 0)
            {
                return;
            }

            index = Mathf.Clamp(index, 0, presets.Length - 1);
            WeatherPreset preset = presets[index];

            if (activeParticleSystem != null)
            {
                Destroy(activeParticleSystem.gameObject);
            }

            if (preset.particlePrefab != null)
            {
                activeParticleSystem = Instantiate(preset.particlePrefab, transform);
            }

            RenderSettings.fogColor = preset.fogColor;
            RenderSettings.fogDensity = preset.fogDensity;
        }
    }
}

using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Rotates a directional light around the city to simulate time of day.
    /// </summary>
    public class DayNightCycle : MonoBehaviour
    {
        [SerializeField] private Light sun;
        [SerializeField] private float dayLengthMinutes = 20f;
        [SerializeField] private Gradient ambientColor;

        private float timeOfDay;

        private void Start()
        {
            timeOfDay = 10f / 24f;
        }

        private void Update()
        {
            if (sun == null)
            {
                return;
            }

            float rotationSpeed = 360f / (dayLengthMinutes * 60f);
            sun.transform.Rotate(Vector3.right, rotationSpeed * Time.deltaTime, Space.World);
            timeOfDay = Mathf.Repeat(timeOfDay + Time.deltaTime / (dayLengthMinutes * 60f), 1f);

            RenderSettings.ambientLight = ambientColor.Evaluate(timeOfDay);
        }
    }
}

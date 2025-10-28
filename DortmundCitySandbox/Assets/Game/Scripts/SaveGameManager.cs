using System.IO;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Stores lightweight save data such as airship location and weather seed.
    /// </summary>
    public class SaveGameManager : MonoBehaviour
    {
        [System.Serializable]
        private struct SaveData
        {
            public Vector3 airshipPosition;
            public float timeOfDay;
            public int weatherIndex;
        }

        [SerializeField] private AirshipController airship;
        [SerializeField] private DayNightCycle dayNightCycle;
        [SerializeField] private WeatherSystem weatherSystem;

        private string SavePath => Path.Combine(Application.persistentDataPath, "dcs_save.json");

        public void Save()
        {
            SaveData data = new()
            {
                airshipPosition = airship != null ? airship.transform.position : Vector3.zero,
                timeOfDay = Time.time,
                weatherIndex = 0
            };

            string json = JsonUtility.ToJson(data, true);
            File.WriteAllText(SavePath, json);
        }

        public void Load()
        {
            if (!File.Exists(SavePath))
            {
                return;
            }

            string json = File.ReadAllText(SavePath);
            SaveData data = JsonUtility.FromJson<SaveData>(json);

            if (airship != null)
            {
                airship.transform.position = data.airshipPosition;
            }
        }
    }
}

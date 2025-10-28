using System.Collections.Generic;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Handles additive loading of city tiles around the player.
    /// </summary>
    public class StreamingManager : MonoBehaviour
    {
        [System.Serializable]
        public class CityTile
        {
            public string sceneName;
            public Vector2Int index;
        }

        [SerializeField] private Transform player;
        [SerializeField] private int loadRadius = 1;
        [SerializeField] private List<CityTile> tiles = new();

        private readonly HashSet<string> loadedScenes = new();

        private void Update()
        {
            if (player == null)
            {
                return;
            }

            Vector2Int playerTile = new(Mathf.RoundToInt(player.position.x / 500f), Mathf.RoundToInt(player.position.z / 500f));
            foreach (var tile in tiles)
            {
                bool shouldBeLoaded = Mathf.Abs(tile.index.x - playerTile.x) <= loadRadius &&
                                      Mathf.Abs(tile.index.y - playerTile.y) <= loadRadius;

                if (shouldBeLoaded && !loadedScenes.Contains(tile.sceneName))
                {
                    UnityEngine.SceneManagement.SceneManager.LoadSceneAsync(tile.sceneName, UnityEngine.SceneManagement.LoadSceneMode.Additive);
                    loadedScenes.Add(tile.sceneName);
                }
                else if (!shouldBeLoaded && loadedScenes.Contains(tile.sceneName))
                {
                    UnityEngine.SceneManagement.SceneManager.UnloadSceneAsync(tile.sceneName);
                    loadedScenes.Remove(tile.sceneName);
                }
            }
        }
    }
}

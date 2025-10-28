using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Keeps the minimap camera aligned with the player and updates overlays.
    /// </summary>
    public class MinimapController : MonoBehaviour
    {
        [SerializeField] private Transform player;
        [SerializeField] private Camera minimapCamera;
        [SerializeField] private float height = 150f;

        private void LateUpdate()
        {
            if (player == null || minimapCamera == null)
            {
                return;
            }

            Vector3 position = player.position;
            position.y += height;
            minimapCamera.transform.position = position;
            minimapCamera.transform.rotation = Quaternion.Euler(90f, player.eulerAngles.y, 0f);
        }
    }
}

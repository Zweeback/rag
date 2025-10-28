using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Simplified wheeled vehicle controller for playable and AI-driven cars.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class VehicleController : MonoBehaviour
    {
        [SerializeField] private float acceleration = 12f;
        [SerializeField] private float steering = 35f;
        [SerializeField] private bool isPlayerControlled;

        private Rigidbody rb;
        private float currentSpeed;

        private void Awake()
        {
            rb = GetComponent<Rigidbody>();
            rb.centerOfMass = new Vector3(0f, -0.5f, 0f);
        }

        private void FixedUpdate()
        {
            float throttle = isPlayerControlled ? Input.GetAxis("Vertical") : 1f;
            float steer = isPlayerControlled ? Input.GetAxis("Horizontal") : 0f;

            currentSpeed += throttle * acceleration * Time.fixedDeltaTime;
            currentSpeed = Mathf.Clamp(currentSpeed, -10f, 40f);

            Vector3 forwardMove = transform.forward * currentSpeed;
            rb.velocity = Vector3.Lerp(rb.velocity, forwardMove, 0.5f);

            Quaternion steerRotation = Quaternion.Euler(0f, steer * steering * Time.fixedDeltaTime, 0f);
            rb.MoveRotation(rb.rotation * steerRotation);
        }
    }
}

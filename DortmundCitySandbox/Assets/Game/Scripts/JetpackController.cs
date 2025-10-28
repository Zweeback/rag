using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Provides toggled vertical thrust with limited fuel to explore the airship and city skyline.
    /// </summary>
    public class JetpackController : MonoBehaviour
    {
        [SerializeField] private float thrustForce = 12f;
        [SerializeField] private float fuelCapacity = 30f;
        [SerializeField] private float fuelRechargeRate = 5f;

        private float currentFuel;
        private bool isActive;
        private Rigidbody rb;

        public bool IsActive => isActive;

        private void Awake()
        {
            rb = GetComponent<Rigidbody>();
            currentFuel = fuelCapacity;
        }

        private void FixedUpdate()
        {
            if (!isActive)
            {
                RechargeFuel();
                return;
            }

            if (currentFuel <= 0f)
            {
                isActive = false;
                return;
            }

            Vector3 thrust = Vector3.up * thrustForce;
            rb.AddForce(thrust, ForceMode.Acceleration);
            currentFuel -= Time.fixedDeltaTime;
        }

        private void RechargeFuel()
        {
            currentFuel = Mathf.Min(fuelCapacity, currentFuel + fuelRechargeRate * Time.fixedDeltaTime);
        }

        public void Toggle()
        {
            if (isActive)
            {
                isActive = false;
                return;
            }

            if (currentFuel > 1f)
            {
                isActive = true;
            }
        }
    }
}

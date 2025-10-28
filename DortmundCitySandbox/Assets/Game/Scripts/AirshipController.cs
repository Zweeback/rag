using System.Collections.Generic;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Controls the Bruce Manor airship autopilot, maintaining altitude and visiting waypoints.
    /// </summary>
    [RequireComponent(typeof(Rigidbody))]
    public class AirshipController : MonoBehaviour
    {
        [SerializeField] private float cruiseAltitude = 250f;
        [SerializeField] private float moveSpeed = 20f;
        [SerializeField] private float rotationSpeed = 10f;
        [SerializeField] private List<Transform> waypoints = new();
        [SerializeField] private Transform dockAnchor;

        private int currentWaypointIndex;
        private bool returningHome;
        private Rigidbody rb;

        private void Awake()
        {
            rb = GetComponent<Rigidbody>();
            rb.useGravity = false;
        }

        private void FixedUpdate()
        {
            MaintainAltitude();
            NavigateRoute();
        }

        private void MaintainAltitude()
        {
            float altitudeError = cruiseAltitude - transform.position.y;
            rb.AddForce(Vector3.up * altitudeError, ForceMode.Acceleration);
        }

        private void NavigateRoute()
        {
            Transform target = returningHome && dockAnchor != null
                ? dockAnchor
                : GetOrLoopWaypoint();

            if (target == null)
            {
                return;
            }

            Vector3 direction = (target.position - transform.position);
            if (direction.sqrMagnitude < 10f)
            {
                AdvanceWaypoint();
                return;
            }

            Vector3 planarDirection = Vector3.ProjectOnPlane(direction, Vector3.up).normalized;
            rb.MovePosition(transform.position + planarDirection * moveSpeed * Time.fixedDeltaTime);
            Quaternion lookRotation = Quaternion.LookRotation(planarDirection, Vector3.up);
            rb.MoveRotation(Quaternion.Slerp(rb.rotation, lookRotation, rotationSpeed * Time.fixedDeltaTime));
        }

        private Transform GetOrLoopWaypoint()
        {
            if (waypoints.Count == 0)
            {
                return dockAnchor;
            }

            currentWaypointIndex %= waypoints.Count;
            return waypoints[currentWaypointIndex];
        }

        private void AdvanceWaypoint()
        {
            if (returningHome)
            {
                returningHome = false;
                currentWaypointIndex = 0;
                return;
            }

            currentWaypointIndex = (currentWaypointIndex + 1) % Mathf.Max(1, waypoints.Count);
        }

        public void ReturnHome()
        {
            returningHome = true;
        }
    }
}

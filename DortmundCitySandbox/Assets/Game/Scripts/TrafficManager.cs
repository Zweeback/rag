using System.Collections.Generic;
using UnityEngine;

namespace DortmundCitySandbox.Gameplay
{
    /// <summary>
    /// Coordinates autonomous vehicles following looped splines around the city tile.
    /// </summary>
    public class TrafficManager : MonoBehaviour
    {
        [SerializeField] private List<VehicleController> vehicles = new();
        [SerializeField] private List<Transform> circuitWaypoints = new();
        [SerializeField] private float waypointTolerance = 5f;

        private void FixedUpdate()
        {
            foreach (var vehicle in vehicles)
            {
                AdvanceVehicle(vehicle);
            }
        }

        private void AdvanceVehicle(VehicleController vehicle)
        {
            if (vehicle == null || circuitWaypoints.Count == 0)
            {
                return;
            }

            TrafficWaypointFollower follower = vehicle.GetComponent<TrafficWaypointFollower>();
            if (follower == null)
            {
                follower = vehicle.gameObject.AddComponent<TrafficWaypointFollower>();
                follower.Configure(circuitWaypoints, waypointTolerance);
            }

            follower.Tick();
        }
    }

    /// <summary>
    /// Helper behaviour enabling reuse between player and AI vehicles.
    /// </summary>
    public class TrafficWaypointFollower : MonoBehaviour
    {
        private List<Transform> waypoints = new();
        private int index;
        private float tolerance = 5f;

        public void Configure(List<Transform> points, float waypointTolerance)
        {
            waypoints = points;
            tolerance = waypointTolerance;
        }

        public void Tick()
        {
            if (waypoints == null || waypoints.Count == 0)
            {
                return;
            }

            Transform target = waypoints[index];
            Vector3 planar = Vector3.ProjectOnPlane(target.position - transform.position, Vector3.up);
            if (planar.sqrMagnitude < tolerance * tolerance)
            {
                index = (index + 1) % waypoints.Count;
            }
        }
    }
}

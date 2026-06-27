import 'package:flutter/material.dart';
import '../models/event_model.dart';

class EventCard extends StatelessWidget {

  final Event event;

  const EventCard({
    super.key,
    required this.event,
  });

  @override
  Widget build(BuildContext context) {

    return Card(
      margin: const EdgeInsets.all(10),

      child: ListTile(
        leading: const Icon(Icons.event),

        title: Text(event.title),

        subtitle: Column(
          crossAxisAlignment:
          CrossAxisAlignment.start,

          children: [

            Text(event.category),

            Text(
              "${event.distanceKm} km away",
            ),

            Text(event.locationName),
          ],
        ),
      ),
    );
  }
}
import 'package:flutter/material.dart';

void main() {
  runApp(const SystemOneApp());
}

/// Root widget. Placeholder from S1V2-01-002 (repository structuring) — the
/// real onboarding/device/automation UI is scoped to later S1V2-06-* tasks.
class SystemOneApp extends StatelessWidget {
  const SystemOneApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SystemONE',
      home: Scaffold(
        appBar: AppBar(title: const Text('SystemONE')),
        body: const Center(child: Text('SystemONE Customer App — Skeleton')),
      ),
    );
  }
}

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:systemone_customer_app/main.dart';

void main() {
  testWidgets('SystemOneApp shows the skeleton placeholder', (tester) async {
    await tester.pumpWidget(const SystemOneApp());

    expect(find.text('SystemONE'), findsOneWidget);
    expect(find.text('SystemONE Customer App — Skeleton'), findsOneWidget);
  });
}

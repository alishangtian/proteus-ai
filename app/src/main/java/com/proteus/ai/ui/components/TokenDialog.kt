package com.proteus.ai.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import com.proteus.ai.R

@Composable
fun TokenDialog(
    onDismissRequest: () -> Unit,
    onConfirm: (String) -> Unit,
    initialToken: String = ""
) {
    var tokenState by remember { mutableStateOf(TextFieldValue(initialToken)) }

    Dialog(onDismissRequest = onDismissRequest) {
        Surface(
            shape = MaterialTheme.shapes.medium,
            tonalElevation = 6.dp,
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Text(
                    text = stringResource(R.string.token_settings),
                    style = MaterialTheme.typography.headlineSmall,
                    modifier = Modifier.padding(bottom = 16.dp)
                )
                OutlinedTextField(
                    value = tokenState,
                    onValueChange = { tokenState = it },
                    label = { Text(stringResource(R.string.enter_token)) },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true
                )
                Spacer(modifier = Modifier.height(24.dp))
                Row(
                    horizontalArrangement = Arrangement.End,
                    modifier = Modifier.fillMaxWidth()
                ) {
                    TextButton(
                        onClick = onDismissRequest,
                        modifier = Modifier.padding(end = 8.dp)
                    ) {
                        Text(stringResource(R.string.cancel))
                    }
                    Button(
                        onClick = { onConfirm(tokenState.text) },
                        enabled = tokenState.text.isNotBlank()
                    ) {
                        Text(stringResource(R.string.save))
                    }
                }
            }
        }
    }
}